from __future__ import annotations

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
