from __future__ import annotations

from pathlib import Path

from app import pdf_tools


def test_flatten_tolerates_pdfcpu_in_place_output(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4 source")
    dest = tmp_path / "dest.pdf"

    monkeypatch.setattr(pdf_tools, "tool_available", lambda name: True)
    monkeypatch.setattr(pdf_tools, "_fill_with_pypdf", lambda s, d, v: d.write_bytes(b"%PDF-1.4 filled"))

    def fake_run(cmd: list[str], timeout: int = 120) -> None:
        if "fill" in cmd:
            Path(cmd[-1]).write_bytes(b"%PDF-1.4 filled")
        if "flatten" in cmd:
            Path(cmd[3]).write_bytes(b"%PDF-1.4 flattened in place")

    monkeypatch.setattr(pdf_tools, "_run", fake_run)

    pdf_tools.fill_pdf(
        source=source,
        dest=dest,
        values={"name": "Ada"},
        regenerate_appearance=False,
        flatten=True,
    )

    assert dest.exists()
    assert b"flattened in place" in dest.read_bytes()
