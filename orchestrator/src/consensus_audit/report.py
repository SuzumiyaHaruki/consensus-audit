from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import utc_now, write_json


CANDIDATE_STATUSES = {
    "candidate_found",
    "no_candidate",
    "insufficient_evidence",
}

REQUIRED_TOP_LEVEL_KEYS = {
    "status",
    "property_id",
    "property_statement",
    "summary",
    "source_evidence",
    "mechanism",
    "causal_chain",
    "test_sketch",
    "uncertainties",
}


@dataclass(frozen=True)
class CandidateArtifacts:
    status: str
    parse_recoverable: bool
    strict_output_compliant: bool
    schema_valid: bool
    provenance_valid: bool
    parsed_file: str | None

    @property
    def format_valid(self) -> bool:
        """Backward-compatible alias for schema validity."""
        return self.schema_valid


def _extract_json_object(
    response: str,
) -> tuple[dict[str, Any] | None, bool, bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = response.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        direct_error = (
            f"response is not one JSON object: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}"
        )
        fenced_objects: list[tuple[dict[str, Any], re.Match[str]]] = []
        pattern = re.compile(
            r"```(?:json)?\s*(.*?)\s*```",
            flags=re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(text):
            try:
                fenced_value = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(fenced_value, dict):
                fenced_objects.append((fenced_value, match))
        if len(fenced_objects) == 1:
            parsed, match = fenced_objects[0]
            warnings.append("extracted the unique JSON object from a code fence")
            surrounding = text[: match.start()] + text[match.end() :]
            if surrounding.strip():
                warnings.append("ignored surrounding prose outside the JSON code fence")
        elif len(fenced_objects) > 1:
            errors.append("response contains multiple valid JSON code blocks")
            return None, False, False, errors, warnings
        else:
            decoder = json.JSONDecoder()
            prose_objects: list[dict[str, Any]] = []
            for start in (match.start() for match in re.finditer(r"[{]", text)):
                try:
                    value, end = decoder.raw_decode(text[start:])
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict) and not text[start + end :].strip():
                    prose_objects.append(value)
            if len(prose_objects) == 1:
                parsed = prose_objects[0]
                warnings.append("extracted the unique JSON object following prose")
            elif len(prose_objects) > 1:
                errors.append("response contains multiple recoverable JSON objects")
                return None, False, False, errors, warnings
            else:
                errors.append(direct_error)
                return None, False, False, errors, warnings
        strict_output_compliant = False
        parse_recoverable = True
    else:
        strict_output_compliant = True
        parse_recoverable = isinstance(parsed, dict)
    if not isinstance(parsed, dict):
        errors.append("Candidate-v0 output must be a JSON object")
        return None, False, strict_output_compliant, errors, warnings
    return parsed, parse_recoverable, strict_output_compliant, errors, warnings


def _require_nonempty_string(
    value: Any,
    field: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")


def _validate_string_list(
    value: Any,
    field: str,
    errors: list[str],
    *,
    minimum: int = 0,
) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list of strings")
        return
    if len(value) < minimum:
        errors.append(f"{field} must contain at least {minimum} item(s)")
    for index, item in enumerate(value):
        _require_nonempty_string(item, f"{field}[{index}]", errors)


def _validate_source_evidence(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("source_evidence must be a list")
        return
    for index, item in enumerate(value):
        prefix = f"source_evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _require_nonempty_string(item.get("path"), f"{prefix}.path", errors)
        start = item.get("start_line")
        end = item.get("end_line")
        if not isinstance(start, int) or isinstance(start, bool) or start <= 0:
            errors.append(f"{prefix}.start_line must be a positive integer")
        if not isinstance(end, int) or isinstance(end, bool) or end <= 0:
            errors.append(f"{prefix}.end_line must be a positive integer")
        if isinstance(start, int) and isinstance(end, int) and start > end:
            errors.append(f"{prefix}.start_line must not exceed end_line")
        _require_nonempty_string(item.get("claim"), f"{prefix}.claim", errors)


def validate_candidate_format(
    candidate: dict[str, Any],
    *,
    audit_mode: str,
    expected_property_id: str | None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - candidate.keys())
    if missing:
        errors.append("missing required field(s): " + ", ".join(missing))
    extra = sorted(candidate.keys() - REQUIRED_TOP_LEVEL_KEYS)
    if extra:
        warnings.append("unrecognized field(s): " + ", ".join(extra))

    status = candidate.get("status")
    if status not in CANDIDATE_STATUSES:
        errors.append(
            "status must be candidate_found, no_candidate, or insufficient_evidence"
        )

    property_id = candidate.get("property_id")
    if property_id is not None and not isinstance(property_id, str):
        errors.append("property_id must be a string or null")
    if audit_mode == "property-directed":
        if not expected_property_id:
            errors.append("property-directed validation requires an expected property ID")
        elif property_id != expected_property_id:
            errors.append(
                f"property_id must equal the selected property {expected_property_id!r}"
            )
    elif audit_mode == "matched-no-property":
        if property_id is not None:
            errors.append("property_id must be null in matched-no-property mode")
    else:
        errors.append(f"unsupported audit mode {audit_mode!r}")

    _require_nonempty_string(
        candidate.get("property_statement"), "property_statement", errors
    )
    _require_nonempty_string(candidate.get("summary"), "summary", errors)
    _validate_source_evidence(candidate.get("source_evidence"), errors)
    _validate_string_list(candidate.get("uncertainties"), "uncertainties", errors)

    if status == "candidate_found":
        evidence = candidate.get("source_evidence")
        if isinstance(evidence, list) and not evidence:
            errors.append("candidate_found requires at least one source_evidence item")

        mechanism = candidate.get("mechanism")
        if not isinstance(mechanism, dict):
            errors.append("candidate_found requires a mechanism object")
        else:
            _require_nonempty_string(
                mechanism.get("violated_obligation"),
                "mechanism.violated_obligation",
                errors,
            )
            _require_nonempty_string(
                mechanism.get("decisive_relation"),
                "mechanism.decisive_relation",
                errors,
            )

        _validate_string_list(
            candidate.get("causal_chain"), "causal_chain", errors, minimum=2
        )

        sketch = candidate.get("test_sketch")
        if not isinstance(sketch, dict):
            errors.append("candidate_found requires a test_sketch object")
        else:
            _require_nonempty_string(
                sketch.get("precondition"), "test_sketch.precondition", errors
            )
            _validate_string_list(
                sketch.get("actions"), "test_sketch.actions", errors, minimum=1
            )
            _require_nonempty_string(
                sketch.get("violation"), "test_sketch.violation", errors
            )
            _require_nonempty_string(sketch.get("oracle"), "test_sketch.oracle", errors)
    elif status in {"no_candidate", "insufficient_evidence"}:
        if candidate.get("mechanism") is not None:
            errors.append(f"{status} requires mechanism to be null")
        chain = candidate.get("causal_chain")
        if chain != []:
            errors.append(f"{status} requires an empty causal_chain")
        if candidate.get("test_sketch") is not None:
            errors.append(f"{status} requires test_sketch to be null")

    return errors, warnings


def _read_ranges(evidence_manifest: dict[str, Any]) -> dict[str, list[tuple[int, int]]]:
    result: dict[str, list[tuple[int, int]]] = {}
    files = evidence_manifest.get("files")
    if not isinstance(files, dict):
        return result
    entries = files.get("read")
    if not isinstance(entries, list):
        return result
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        ranges: list[tuple[int, int]] = []
        for item in entry.get("ranges", []):
            if not isinstance(item, dict):
                continue
            start, end = item.get("start"), item.get("end")
            if isinstance(start, int) and isinstance(end, int):
                ranges.append((start, end))
        result[entry["path"]] = ranges
    return result


def _range_is_covered(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    cursor = start
    for range_start, range_end in sorted(ranges):
        if range_end < cursor:
            continue
        if range_start > cursor:
            return False
        cursor = max(cursor, range_end + 1)
        if cursor > end:
            return True
    return False


def validate_candidate_provenance(
    candidate: dict[str, Any],
    *,
    target_root: Path,
    evidence_manifest: dict[str, Any],
) -> dict[str, Any]:
    root = target_root.resolve()
    ranges_by_path = _read_ranges(evidence_manifest)
    errors: list[str] = []
    checked: list[dict[str, Any]] = []
    evidence = candidate.get("source_evidence")
    if not isinstance(evidence, list):
        evidence = []

    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        start = item.get("start_line")
        end = item.get("end_line")
        prefix = f"source_evidence[{index}]"
        path_object = Path(path)
        exists = False
        inside_target = False
        if path_object.is_absolute() or ".." in path_object.parts or ".git" in path_object.parts:
            errors.append(f"{prefix}.path is not a permitted target-relative path: {path!r}")
        else:
            resolved = (root / path_object).resolve()
            try:
                resolved.relative_to(root)
                inside_target = True
            except ValueError:
                errors.append(f"{prefix}.path escapes TARGET_ROOT: {path!r}")
            if inside_target:
                exists = resolved.is_file()
                if not exists:
                    errors.append(f"{prefix}.path is not an existing file: {path!r}")

        read_ranges = ranges_by_path.get(path, [])
        covered = False
        if isinstance(start, int) and isinstance(end, int):
            covered = _range_is_covered(start, end, read_ranges)
            if not covered:
                errors.append(
                    f"{prefix} range {path}:{start}-{end} was not fully read during this run"
                )
        checked.append(
            {
                "index": index,
                "path": path,
                "start_line": start,
                "end_line": end,
                "path_exists": exists,
                "covered_by_read_file": covered,
            }
        )

    return {
        "schema_version": "candidate-provenance-validation/v1",
        "generated_at": utc_now(),
        "valid": not errors,
        "errors": errors,
        "checked_references": checked,
        "evidence_policy": (
            "every cited interval must be fully covered by read_file evidence "
            "from this run"
        ),
    }


def write_candidate_artifacts(
    run_directory: Path,
    response: str,
    *,
    target_root: Path,
    evidence_manifest: dict[str, Any],
    audit_mode: str,
    expected_property_id: str | None,
) -> CandidateArtifacts:
    candidate, parse_recoverable, strict_output_compliant, parse_errors, warnings = (
        _extract_json_object(response)
    )
    validation_errors = list(parse_errors)
    if candidate is not None:
        errors, schema_warnings = validate_candidate_format(
            candidate,
            audit_mode=audit_mode,
            expected_property_id=expected_property_id,
        )
        validation_errors.extend(errors)
        warnings.extend(schema_warnings)

    schema_valid = candidate is not None and not validation_errors
    format_validation = {
        "schema_version": "candidate-format-validation/v1",
        "generated_at": utc_now(),
        "valid": schema_valid,
        "parse_recoverable": parse_recoverable,
        "strict_output_compliant": strict_output_compliant,
        "schema_valid": schema_valid,
        "errors": validation_errors,
        "warnings": warnings,
        "audit_mode": audit_mode,
        "expected_property_id": expected_property_id,
    }
    write_json(run_directory / "candidate-format-validation.json", format_validation)

    if not schema_valid:
        write_json(
            run_directory / "candidate-provenance-validation.json",
            {
                "schema_version": "candidate-provenance-validation/v1",
                "generated_at": utc_now(),
                "valid": False,
                "skipped": True,
                "errors": ["provenance validation skipped because Candidate-v0 format is invalid"],
                "checked_references": [],
            },
        )
        return CandidateArtifacts("invalid_output", parse_recoverable, strict_output_compliant, False, False, None)

    write_json(run_directory / "parsed-candidate.json", candidate)
    provenance = validate_candidate_provenance(
        candidate,
        target_root=target_root,
        evidence_manifest=evidence_manifest,
    )
    write_json(run_directory / "candidate-provenance-validation.json", provenance)
    return CandidateArtifacts(
        str(candidate["status"]),
        parse_recoverable,
        strict_output_compliant,
        True,
        bool(provenance["valid"]),
        "parsed-candidate.json",
    )


class CandidateRevalidationError(ValueError):
    """Raised when an existing run cannot be revalidated."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateRevalidationError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateRevalidationError(f"expected a JSON object in {path}")
    return value


def revalidate_candidate_artifacts(run_directory: Path) -> CandidateArtifacts:
    run = run_directory.resolve()
    if not run.is_dir():
        raise CandidateRevalidationError(f"run directory does not exist: {run}")
    request = _load_json_object(run / "request.json")
    evidence_manifest = _load_json_object(run / "evidence-manifest.json")
    try:
        response = (run / "response.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise CandidateRevalidationError(f"cannot read response.md in {run}: {exc}") from exc
    target_root = request.get("target_root")
    audit_mode = request.get("audit_mode")
    if not isinstance(target_root, str) or not target_root:
        raise CandidateRevalidationError("request.json has no target_root")
    if not isinstance(audit_mode, str) or not audit_mode:
        raise CandidateRevalidationError("request.json has no audit_mode")
    expected_property_id = request.get("property_id")
    if expected_property_id is not None and not isinstance(expected_property_id, str):
        raise CandidateRevalidationError("request.json property_id must be a string or null")

    artifacts = write_candidate_artifacts(
        run,
        response,
        target_root=Path(target_root),
        evidence_manifest=evidence_manifest,
        audit_mode=audit_mode,
        expected_property_id=expected_property_id,
    )
    summary_path = run / "summary.json"
    if summary_path.is_file():
        summary = _load_json_object(summary_path)
        summary.update(
            {
                "candidate_status": artifacts.status,
                "candidate_format_valid": artifacts.format_valid,
                "candidate_provenance_valid": artifacts.provenance_valid,
                "parsed_candidate_file": artifacts.parsed_file,
                "candidate_revalidated_at": utc_now(),
            }
        )
        write_json(summary_path, summary)
    return artifacts
