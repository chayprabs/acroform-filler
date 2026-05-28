from __future__ import annotations

import csv
import io
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PASSWORD_PATTERN = re.compile(r"(password|passwd|pwd)[\"']?\s*[:=]\s*[^\s,}]+", re.I)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = PASSWORD_PATTERN.sub("[REDACTED]", record.msg)
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def parse_fdf(data: bytes) -> dict[str, str]:
    text = data.decode("latin-1", errors="ignore")
    values: dict[str, str] = {}
    for match in re.finditer(r"/T\s*\(([^)]+)\)\s*/V\s*\(([^)]*)\)", text):
        values[match.group(1)] = match.group(2)
    return values


def parse_xfdf(data: bytes) -> dict[str, str]:
    root = ET.fromstring(data)
    values: dict[str, str] = {}
    for field in root.findall(".//{http://ns.adobe.com/xfdf/}field"):
        name = field.attrib.get("name")
        value_el = field.find("{http://ns.adobe.com/xfdf/}value")
        if name and value_el is not None and value_el.text is not None:
            values[name] = value_el.text
    return values


def parse_json_values(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("422_FIELD_VALUE_INVALID")
    return payload


def parse_csv_mapping(data: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    return [dict(row) for row in reader]


def parse_import_file(filename: str, data: bytes) -> dict[str, str]:
    lower = filename.lower()
    if lower.endswith(".json"):
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("422_FIELD_VALUE_INVALID")
        return {str(k): str(v) for k, v in payload.items()}
    if lower.endswith(".fdf"):
        return parse_fdf(data)
    if lower.endswith(".xfdf"):
        return parse_xfdf(data)
    raise ValueError("422_FIELD_VALUE_INVALID")


def create_batch_zip(pairs: list[tuple[str, Path]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in pairs:
            archive.write(path, arcname=name)
    return buffer.getvalue()
