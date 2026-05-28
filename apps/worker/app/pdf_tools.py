from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import settings


def _run(cmd: list[str], timeout: int = 120) -> None:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(detail)


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def repair_pdf(source: Path, dest: Path) -> None:
    if not tool_available(settings.qpdf_path):
        shutil.copyfile(source, dest)
        return
    _run([settings.qpdf_path, "--linearize", str(source), str(dest)])


def fill_pdf(
    source: Path,
    dest: Path,
    values: dict[str, str],
    regenerate_appearance: bool,
    flatten: bool,
) -> None:
    working = dest.parent / "working.pdf"
    shutil.copyfile(source, working)

    if tool_available(settings.pdfcpu_path):
        form_file = dest.parent / "form.json"
        form_file.write_text(
            __import__("json").dumps({"forms": values}),
            encoding="utf-8",
        )
        cmd = [settings.pdfcpu_path, "form", "fill", str(working), str(form_file), str(dest)]
        try:
            _run(cmd)
        except RuntimeError:
            _fill_with_pypdf(working, dest, values)
    else:
        _fill_with_pypdf(working, dest, values)

    if regenerate_appearance and tool_available(settings.pdfcpu_path):
        regen = dest.parent / "regen.pdf"
        try:
            _run([settings.pdfcpu_path, "form", "reset", str(dest), str(regen)])
            shutil.move(regen, dest)
        except RuntimeError:
            pass

    if flatten:
        flattened = dest.parent / "flat.pdf"
        if tool_available(settings.pdfcpu_path):
            try:
                _run([settings.pdfcpu_path, "form", "flatten", str(dest), str(flattened)])
                if flattened.exists():
                    try:
                        shutil.move(flattened, dest)
                        return
                    except FileNotFoundError:
                        if dest.exists():
                            return
                if dest.exists():
                    # Some pdfcpu versions flatten in place even when an output is provided.
                    return
            except RuntimeError:
                pass
        _flatten_with_pypdf(dest, flattened)
        if not flattened.exists():
            raise RuntimeError("Flatten output missing after fallback.")
        shutil.move(flattened, dest)


def _fill_with_pypdf(source: Path, dest: Path, values: dict[str, str]) -> None:
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values, auto_regenerate=False)
    buffer = BytesIO()
    writer.write(buffer)
    dest.write_bytes(buffer.getvalue())


def _flatten_with_pypdf(source: Path, dest: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        if "/Annots" in page:
            del page["/Annots"]
    writer.write(str(dest))
