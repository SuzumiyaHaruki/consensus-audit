from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from typing import Any

from consensus_audit.deepseek import (
    DeepSeekClient,
    DeepSeekConfig,
    DeepSeekError,
    read_api_key_file,
)


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout_seconds,
            }
        )
        return {
            "id": "response-1",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "reasoning_content": "reasoning",
                        "content": "answer",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
            },
        }


class DeepSeekTests(unittest.TestCase):
    def test_official_defaults_and_thinking_request(self) -> None:
        transport = FakeTransport()
        client = DeepSeekClient(
            DeepSeekConfig(api_key="test-key"), transport=transport
        )
        response = client.create_chat_completion(
            [{"role": "user", "content": "hello"}], []
        )

        request = transport.requests[0]
        self.assertEqual(request["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(request["payload"]["model"], "deepseek-v4-flash")
        self.assertEqual(request["payload"]["thinking"], {"type": "enabled"})
        self.assertEqual(request["payload"]["reasoning_effort"], "high")
        self.assertNotIn("temperature", request["payload"])
        self.assertEqual(response.reasoning_content, "reasoning")
        self.assertEqual(response.usage["total_tokens"], 14)

    def test_reads_one_raw_key_from_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "deepseek-key.txt"
            path.write_text("test-key\n", encoding="utf-8")
            self.assertEqual(read_api_key_file(path), "test-key")

            path.write_text("two keys\nare invalid\n", encoding="utf-8")
            with self.assertRaises(DeepSeekError):
                read_api_key_file(path)

    def test_final_candidate_request_can_preserve_tools_and_force_json(self) -> None:
        transport = FakeTransport()
        client = DeepSeekClient(
            DeepSeekConfig(api_key="test-key"), transport=transport
        )
        tool = {"type": "function", "function": {"name": "read_file"}}

        client.create_chat_completion(
            [{"role": "user", "content": "return JSON"}],
            [tool],
            response_format={"type": "json_object"},
            tool_choice="none",
        )

        payload = transport.requests[0]["payload"]
        self.assertEqual(payload["tools"], [tool])
        self.assertEqual(payload["tool_choice"], "none")
        self.assertEqual(payload["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
