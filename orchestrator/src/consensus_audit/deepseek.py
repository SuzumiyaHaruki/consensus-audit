from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API request or response is invalid."""


def read_api_key_file(path: Path) -> str:
    """Read one raw API key from a UTF-8 text file without logging its value."""
    source = path.expanduser().resolve()
    try:
        value = source.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        raise DeepSeekError(f"cannot read API key file {source}: {exc}") from exc
    if not value:
        raise DeepSeekError(f"API key file is empty: {source}")
    if any(character.isspace() for character in value):
        raise DeepSeekError(
            f"API key file must contain one raw key without internal whitespace: {source}"
        )
    return value


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    thinking: bool = True
    reasoning_effort: str = "high"
    max_tokens: int = 32_768
    timeout_seconds: float = 600.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.api_key:
            raise DeepSeekError("DeepSeek API key is empty")
        if self.reasoning_effort not in {"low", "high", "max"}:
            raise DeepSeekError("reasoning_effort must be low, high, or max")
        if self.max_tokens <= 0:
            raise DeepSeekError("max_tokens must be positive")
        if self.timeout_seconds <= 0:
            raise DeepSeekError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise DeepSeekError("max_retries cannot be negative")


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


class UrllibJsonTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DeepSeekError("DeepSeek returned non-JSON data") from exc
        if not isinstance(data, dict):
            raise DeepSeekError("DeepSeek returned a non-object JSON response")
        return data


@dataclass(frozen=True)
class ChatResponse:
    content: str
    reasoning_content: str | None
    tool_calls: tuple[dict[str, Any], ...]
    finish_reason: str
    usage: dict[str, int]
    response_id: str | None
    model: str | None

    def assistant_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.reasoning_content is not None:
            message["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            message["tool_calls"] = list(self.tool_calls)
        return message


class DeepSeekClient:
    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        transport: JsonTransport | None = None,
        sleep: Any = time.sleep,
    ):
        self.config = config
        self.transport = transport or UrllibJsonTransport()
        self._sleep = sleep

    def _request_body(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        if self.config.thinking:
            body["thinking"] = {"type": "enabled"}
            body["reasoning_effort"] = self.config.reasoning_effort
        else:
            body["thinking"] = {"type": "disabled"}
        return body

    def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatResponse:
        body = self._request_body(messages, tools)
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        last_error: Exception | None = None
        data: dict[str, Any] | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                data = self.transport.post_json(
                    endpoint,
                    headers,
                    body,
                    self.config.timeout_seconds,
                )
                break
            except urllib.error.HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")[:2000]
                last_error = DeepSeekError(f"DeepSeek HTTP {exc.code}: {body_text}")
                retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.config.max_retries:
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, DeepSeekError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise DeepSeekError(f"DeepSeek request failed: {exc}") from exc
            self._sleep(min(2**attempt, 8))

        if data is None:
            raise DeepSeekError(f"DeepSeek request failed: {last_error}")
        return self._parse_response(data)

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise DeepSeekError("DeepSeek response has no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise DeepSeekError("DeepSeek choice is not an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise DeepSeekError("DeepSeek choice has no message")

        raw_content = message.get("content")
        if isinstance(raw_content, str):
            content = raw_content
        elif raw_content is None:
            content = ""
        elif isinstance(raw_content, list):
            content = "".join(
                part.get("text", "")
                for part in raw_content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        else:
            raise DeepSeekError("DeepSeek message content has an unexpected type")

        reasoning = message.get("reasoning_content")
        if reasoning is not None and not isinstance(reasoning, str):
            reasoning = str(reasoning)
        raw_tool_calls = message.get("tool_calls") or []
        if not isinstance(raw_tool_calls, list):
            raise DeepSeekError("DeepSeek tool_calls is not a list")
        tool_calls = tuple(call for call in raw_tool_calls if isinstance(call, dict))

        raw_usage = data.get("usage") or {}
        usage: dict[str, int] = {}
        if isinstance(raw_usage, dict):
            for key, value in raw_usage.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    usage[str(key)] = value

        return ChatResponse(
            content=content,
            reasoning_content=reasoning,
            tool_calls=tool_calls,
            finish_reason=str(choice.get("finish_reason") or ""),
            usage=usage,
            response_id=str(data["id"]) if data.get("id") is not None else None,
            model=str(data["model"]) if data.get("model") is not None else None,
        )
