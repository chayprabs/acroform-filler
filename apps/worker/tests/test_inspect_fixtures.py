from __future__ import annotations

import json
from pathlib import Path

from app.inspect import inspect_pdf


def test_w9_fixture_inspect_extracts_fields_with_bbox() -> None:
    fixture = Path(__file__).resolve().parent.parent / "samples" / "w9.pdf"
    result = inspect_pdf(fixture.read_bytes())

    assert result["pageCount"] >= 1
    assert len(result["fields"]) > 0
    first = result["fields"][0]
    assert isinstance(first["bbox"], list)
    assert len(first["bbox"]) == 4


def test_sample_inspect_snapshot_matches_expected_counts() -> None:
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    snapshot_path = Path(__file__).resolve().parent / "fixtures" / "sample_inspect_snapshot.json"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))

    actual: dict[str, dict[str, int]] = {}
    for sample_name in expected.keys():
        sample_path = samples_dir / sample_name
        result = inspect_pdf(sample_path.read_bytes())
        actual[sample_name] = {"pageCount": int(result["pageCount"]), "fieldCount": len(result["fields"])}

    assert actual == expected
