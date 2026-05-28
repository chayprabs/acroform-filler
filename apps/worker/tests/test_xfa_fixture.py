from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from app.inspect import inspect_pdf


def _build_xfa_only_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)

    acro = DictionaryObject()
    acro[NameObject("/XFA")] = ArrayObject(
        [
            TextStringObject("template"),
            TextStringObject("<xfa:template xmlns:xfa='http://www.xfa.org/schema/xfa-template/3.3/'/>"),
        ]
    )
    acro[NameObject("/Fields")] = ArrayObject()
    writer._root_object[NameObject("/AcroForm")] = writer._add_object(acro)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_real_xfa_only_fixture_returns_non_convertible_error() -> None:
    pdf = _build_xfa_only_pdf()
    try:
        inspect_pdf(pdf)
        raise AssertionError("Expected 409_XFA_NOT_CONVERTIBLE")
    except ValueError as exc:
        assert str(exc) == "409_XFA_NOT_CONVERTIBLE"
