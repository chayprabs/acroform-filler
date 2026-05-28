from __future__ import annotations

import csv
import io
import json
import sys
import tracemalloc
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app


def run_a1(client: TestClient, sample_path: Path) -> dict[str, object]:
    sample = sample_path.read_bytes()
    inspect_response = client.post("/v1/inspect", files={"file": (sample_path.name, sample, "application/pdf")})
    if inspect_response.status_code != 200:
        return {"ok": False, "stage": "inspect", "status": inspect_response.status_code}

    inspect_body = inspect_response.json()
    job_id = inspect_body["jobId"]
    values: dict[str, str] = {}
    for field in inspect_body["fields"][:8]:
        field_name = field["name"]
        field_type = field["type"]
        if field_type in {"text", "combo", "listbox"}:
            values[field_name] = "PdfForms QA"
        elif field_type == "checkbox":
            values[field_name] = "Yes"

    fill_response = client.post(
        "/v1/fill",
        json={"jobId": job_id, "values": values, "regenerateAppearance": True, "flatten": True},
    )
    if fill_response.status_code != 200:
        return {"ok": False, "stage": "fill", "status": fill_response.status_code}

    artifact_url = fill_response.json()["artifact"]["downloadUrl"]
    parsed = urlparse(artifact_url)
    query = parse_qs(parsed.query)
    download_path = parsed.path
    download_response = client.get(
        download_path,
        params={
            "jobId": query["jobId"][0],
            "expiresAt": query["expiresAt"][0],
            "token": query["token"][0],
        },
    )
    return {
        "ok": download_response.status_code == 200 and len(download_response.content) > 1024,
        "stage": "download",
        "status": download_response.status_code,
        "bytes": len(download_response.content),
        "fieldCount": len(inspect_body["fields"]),
    }


def run_a3(client: TestClient, sample_path: Path) -> dict[str, object]:
    sample = sample_path.read_bytes()
    zip_buffer = io.BytesIO()
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["source", "name"])
    writer.writeheader()

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for idx in range(100):
            source = f"batch/sample-{idx:03d}.pdf"
            archive.writestr(source, sample)
            writer.writerow({"source": source, "name": f"User {idx:03d}"})

    tracemalloc.start()
    response = client.post(
        "/v1/batch",
        files={
            "pdf_zip": ("inputs.zip", zip_buffer.getvalue(), "application/zip"),
            "csv_mapping": ("map.csv", csv_buffer.getvalue().encode("utf-8"), "text/csv"),
        },
        data={"regenerate_appearance": "true", "flatten": "true"},
    )
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if response.status_code != 200:
        return {"ok": False, "status": response.status_code, "peakMiB": round(peak_bytes / (1024 * 1024), 2)}

    body = response.json()
    return {
        "ok": body["count"] == 100 and len(body["errors"]) == 0,
        "status": response.status_code,
        "count": body["count"],
        "requested": body["requested"],
        "errors": len(body["errors"]),
        "peakMiB": round(peak_bytes / (1024 * 1024), 2),
    }


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
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def run_a2(client: TestClient) -> dict[str, object]:
    xfa_pdf = _build_xfa_only_pdf()
    response = client.post("/v1/inspect", files={"file": ("xfa-only.pdf", xfa_pdf, "application/pdf")})
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    detail = body.get("detail") if isinstance(body, dict) else {}
    return {
        "ok": response.status_code == 409 and (detail or {}).get("code") == "409_XFA_NOT_CONVERTIBLE",
        "status": response.status_code,
        "code": (detail or {}).get("code"),
        "message": (detail or {}).get("message"),
    }


if __name__ == "__main__":
    client = TestClient(app)
    sample = Path(__file__).resolve().parents[1] / "samples" / "w9.pdf"
    result = {"A1": run_a1(client, sample), "A2": run_a2(client), "A3": run_a3(client, sample)}
    print(json.dumps(result, indent=2))
