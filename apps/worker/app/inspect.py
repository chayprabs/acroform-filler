from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.constants import FieldDictionaryAttributes
from pypdf.errors import PdfReadError
from pypdf.generic import IndirectObject

FIELD_TYPE_MAP = {
    "/Tx": "text",
    "/Btn": "button",
    "/Ch": "combo",
    "/Sig": "signature",
}


def _resolve(obj: Any) -> Any:
    while isinstance(obj, IndirectObject):
        obj = obj.get_object()
    return obj


def _field_type(field: dict[str, Any]) -> str:
    ft = str(field.get(FieldDictionaryAttributes.FT, "/Tx"))
    if ft == "/Btn":
        flags = int(field.get(FieldDictionaryAttributes.Ff, 0))
        if flags & 32768:
            return "radio"
        if flags & 65536:
            return "button"
        return "checkbox"
    if ft == "/Ch":
        flags = int(field.get(FieldDictionaryAttributes.Ff, 0))
        return "listbox" if flags & 131072 else "combo"
    return FIELD_TYPE_MAP.get(ft, "text")


def _field_options(field: dict[str, Any]) -> list[str] | None:
    opts = field.get("/Opt")
    if not opts:
        return None
    resolved = _resolve(opts)
    if isinstance(resolved, list):
        return [str(item[0] if isinstance(item, list) else item) for item in resolved]
    return None


def _field_bbox(field: dict[str, Any], page_height: float) -> list[float]:
    rect = field.get("/Rect")
    if not rect:
        return [0.0, 0.0, 0.0, 0.0]
    x1, y1, x2, y2 = [float(v) for v in rect]
    # Convert PDF bottom-left origin to top-left for pdf.js overlay.
    top = page_height - max(y1, y2)
    left = min(x1, x2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    return [left, top, width, height]


def _page_heights(reader: PdfReader) -> list[float]:
    heights: list[float] = []
    for page in reader.pages:
        box = page.mediabox
        heights.append(float(box.top) - float(box.bottom))
    return heights


def _merge_widget_field(widget: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    parent = widget.get("/Parent")
    parent_resolved = _resolve(parent) if parent else None
    if isinstance(parent_resolved, dict):
        merged.update(parent_resolved)
    merged.update(widget)
    return merged


def _extract_annotation_fields(reader: PdfReader, heights: list[float]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    seen: set[tuple[str, int, tuple[float, float, float, float]]] = set()

    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        annots_resolved = _resolve(annots)
        if not isinstance(annots_resolved, list):
            continue
        page_height = heights[page_index] if page_index < len(heights) else heights[0]
        for annot_obj in annots_resolved:
            annot = _resolve(annot_obj)
            if not isinstance(annot, dict):
                continue
            if str(annot.get("/Subtype")) != "/Widget":
                continue

            field = _merge_widget_field(annot)
            name = field.get("/T")
            if not name:
                continue

            flags = int(field.get(FieldDictionaryAttributes.Ff, 0))
            value = field.get("/V", field.get("/AS"))
            if value is not None:
                value = str(_resolve(value))

            bbox = _field_bbox(field, page_height)
            key = (str(name), page_index + 1, tuple(bbox))
            if key in seen:
                continue
            seen.add(key)

            max_len = field.get("/MaxLen")
            extracted.append(
                {
                    "name": str(name),
                    "type": _field_type(field),
                    "page": page_index + 1,
                    "bbox": bbox,
                    "value": value,
                    "options": _field_options(field),
                    "required": bool(flags & 2),
                    "maxLength": int(max_len) if max_len is not None else None,
                    "readonly": bool(flags & 1),
                }
            )

    return extracted


def detect_xfa(reader: PdfReader) -> tuple[bool, bool]:
    root = reader.trailer.get("/Root")
    if isinstance(root, IndirectObject):
        root = root.get_object()
    if not isinstance(root, dict):
        return False, False
    acro = root.get("/AcroForm")
    if isinstance(acro, IndirectObject):
        acro = acro.get_object()
    if not isinstance(acro, dict):
        return False, False
    has_xfa = "/XFA" in acro
    has_fields = bool(acro.get("/Fields"))
    convertible = has_xfa and has_fields
    return has_xfa, convertible


def inspect_pdf(data: bytes, password: str | None = None) -> dict[str, Any]:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
    except PdfReadError as exc:
        raise ValueError("400_PDF_INVALID") from exc

    if reader.is_encrypted:
        if not password:
            raise ValueError("401_PDF_PASSWORD_REQUIRED")
        if reader.decrypt(password) == 0:
            raise ValueError("401_PDF_PASSWORD_REQUIRED")

    has_xfa, xfa_convertible = detect_xfa(reader)
    warnings: list[str] = []
    if has_xfa and not xfa_convertible:
        warnings.append("XFA-only form detected; conversion may not be possible.")

    heights = _page_heights(reader)
    fields: list[dict[str, Any]] = []

    def walk(field_obj: Any, page_index: int | None = None) -> None:
        field = _resolve(field_obj)
        if not isinstance(field, dict):
            return
        kids = field.get("/Kids")
        if kids:
            for kid in kids:
                walk(kid, page_index)
            return

        name = field.get("/T")
        if not name:
            return

        page_num = page_index if page_index is not None else 0
        page_height = heights[page_num] if page_num < len(heights) else heights[0]
        flags = int(field.get(FieldDictionaryAttributes.Ff, 0))
        max_len = field.get("/MaxLen")
        value = field.get("/V")
        if value is not None:
            value = str(_resolve(value))

        fields.append(
            {
                "name": str(name),
                "type": _field_type(field),
                "page": page_num + 1,
                "bbox": _field_bbox(field, page_height),
                "value": value,
                "options": _field_options(field),
                "required": bool(flags & 2),
                "maxLength": int(max_len) if max_len is not None else None,
                "readonly": bool(flags & 1),
            }
        )

    try:
        form_fields = reader.get_fields() or {}
        for name, field in form_fields.items():
            resolved = _resolve(field)
            if isinstance(resolved, dict):
                resolved.setdefault("/T", name)
            walk(resolved)
    except Exception:
        warnings.append("Partial field extraction; some widgets may be missing.")

    annotation_fields = _extract_annotation_fields(reader, heights)
    if annotation_fields:
        keyed = {(field["name"], field["page"], tuple(field["bbox"])): field for field in fields}
        for field in annotation_fields:
            key = (field["name"], field["page"], tuple(field["bbox"]))
            if key not in keyed:
                fields.append(field)

    if not fields and has_xfa and not xfa_convertible:
        raise ValueError("409_XFA_NOT_CONVERTIBLE")

    return {
        "fields": fields,
        "pageCount": len(reader.pages),
        "hasXfa": has_xfa,
        "xfaConvertible": xfa_convertible,
        "warnings": warnings,
    }
