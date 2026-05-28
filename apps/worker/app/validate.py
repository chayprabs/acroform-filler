from __future__ import annotations

from typing import Any


def validate_values(fields: list[dict[str, Any]], values: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    field_map = {field["name"]: field for field in fields}

    for name, field in field_map.items():
        if field.get("required") and name not in values:
            issues.append(
                {
                    "field": name,
                    "code": "REQUIRED_MISSING",
                    "message": f"Required field '{name}' is missing.",
                }
            )

    for name, raw in values.items():
        field = field_map.get(name)
        if not field:
            continue
        value = "" if raw is None else str(raw)
        max_len = field.get("maxLength")
        if max_len is not None and len(value) > int(max_len):
            issues.append(
                {
                    "field": name,
                    "code": "MAX_LENGTH",
                    "message": f"Value for '{name}' exceeds max length {max_len}.",
                }
            )

        ftype = field.get("type")
        options = field.get("options") or []
        if ftype in {"checkbox", "radio"} and value not in {"Yes", "Off", "true", "false", "1", "0", ""}:
            if options and value not in options:
                issues.append(
                    {
                        "field": name,
                        "code": "INVALID_CHOICE",
                        "message": f"Invalid choice '{value}' for '{name}'.",
                    }
                )
        if ftype in {"listbox", "combo"} and options and value and value not in options:
            issues.append(
                {
                    "field": name,
                    "code": "INVALID_CHOICE",
                    "message": f"Invalid option '{value}' for '{name}'.",
                }
            )
        if ftype == "text" and isinstance(raw, bool):
            issues.append(
                {
                    "field": name,
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected text for '{name}', got boolean.",
                }
            )

    return issues
