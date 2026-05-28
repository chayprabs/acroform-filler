from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.jobs import JobStore
from app.main import app


def _client_with_tmp_store(monkeypatch, tmp_path: Path) -> TestClient:
    store = JobStore(root=tmp_path / "jobs")
    monkeypatch.setattr("app.main.job_store", store)
    return TestClient(app)


def test_inspect_returns_schema(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    def fail_repair(source: Path, dest: Path) -> None:
        raise RuntimeError("should not repair")

    monkeypatch.setattr("app.main.repair_pdf", fail_repair)

    def fake_inspect(data: bytes, password: str | None = None):
        assert data
        assert password == "pw"
        return {
            "fields": [
                {
                    "name": "full_name",
                    "type": "text",
                    "page": 1,
                    "bbox": [10, 20, 30, 10],
                    "required": True,
                    "options": None,
                    "maxLength": 50,
                    "readonly": False,
                    "value": "",
                }
            ],
            "pageCount": 1,
            "hasXfa": False,
            "xfaConvertible": False,
            "warnings": [],
        }

    monkeypatch.setattr("app.main.inspect_pdf", fake_inspect)

    response = client.post(
        "/v1/inspect",
        files={"file": ("sample.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"password": "pw"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"]
    assert payload["fields"][0]["name"] == "full_name"


def test_inspect_retries_after_repair_on_invalid_pdf(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    call_count = {"count": 0}

    def fake_inspect(data: bytes, password: str | None = None):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise ValueError("400_PDF_INVALID")
        return {
            "fields": [],
            "pageCount": 1,
            "hasXfa": False,
            "xfaConvertible": False,
            "warnings": [],
        }

    monkeypatch.setattr("app.main.inspect_pdf", fake_inspect)
    monkeypatch.setattr("app.main.repair_pdf", lambda source, dest: dest.write_bytes(source.read_bytes()))

    response = client.post("/v1/inspect", files={"file": ("sample.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert response.status_code == 200
    assert call_count["count"] == 2


def test_samples_endpoint_lists_and_serves_files(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    for sample_name in ["w9.pdf", "i9.pdf", "registration.pdf", "multi-page.pdf"]:
        (samples_dir / sample_name).write_bytes(b"%PDF-1.4 sample")

    monkeypatch.setattr("app.main.settings.samples_dir", str(samples_dir))

    listed = client.get("/v1/samples")
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()["samples"]} == {"w9", "i9", "registration", "multi-page"}

    fetched = client.get("/v1/samples/w9")
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "application/pdf"


def test_validate_and_fill_emit_required_warning(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    store: JobStore = main_module.job_store

    job = store.create()
    source = store.artifact_path(job, "source.pdf")
    source.write_bytes(b"%PDF-1.4")
    job.source_pdf = source
    job.fields = [{"name": "required_text", "type": "text", "required": True}]
    store.save_metadata(job)

    monkeypatch.setattr("app.main.fill_pdf", lambda **kwargs: Path(kwargs["dest"]).write_bytes(b"%PDF-1.4 filled"))

    validate_response = client.post("/v1/validate", json={"jobId": job.job_id, "values": {}})
    assert validate_response.status_code == 200
    assert validate_response.json()["issues"][0]["code"] == "REQUIRED_MISSING"

    fill_response = client.post(
        "/v1/fill",
        json={
            "jobId": job.job_id,
            "values": {},
            "regenerateAppearance": True,
            "flatten": True,
        },
    )
    assert fill_response.status_code == 200
    body = fill_response.json()
    assert body["warnings"]
    assert "REQUIRED_MISSING" in {issue["code"] for issue in body["issues"]}


def test_import_json_file(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    response = client.post(
        "/v1/import",
        files={"file": ("values.json", b'{"first_name":"Ada"}', "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["values"]["first_name"] == "Ada"


def test_import_fdf_and_xfdf_files(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    fdf = b"%FDF-1.2\n1 0 obj<< /FDF << /Fields [<< /T (name) /V (Ada) >>] >> >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    xfdf = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<xfdf xmlns="http://ns.adobe.com/xfdf/"><fields><field name="email"><value>a@example.com</value>'
        b"</field></fields></xfdf>"
    )

    fdf_response = client.post("/v1/import", files={"file": ("values.fdf", fdf, "application/vnd.fdf")})
    xfdf_response = client.post("/v1/import", files={"file": ("values.xfdf", xfdf, "application/xml")})

    assert fdf_response.status_code == 200
    assert xfdf_response.status_code == 200
    assert fdf_response.json()["values"]["name"] == "Ada"
    assert xfdf_response.json()["values"]["email"] == "a@example.com"


def test_inspect_xfa_only_returns_friendly_error(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    monkeypatch.setattr("app.main.repair_pdf", lambda source, dest: dest.write_bytes(source.read_bytes()))
    def fake_inspect(data: bytes, password: str | None = None):
        raise ValueError("409_XFA_NOT_CONVERTIBLE")
    monkeypatch.setattr("app.main.inspect_pdf", fake_inspect)

    response = client.post("/v1/inspect", files={"file": ("xfa.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "409_XFA_NOT_CONVERTIBLE"
    assert "XFA-only" in response.json()["detail"]["message"]


def test_inspect_xfa_attempts_sidecar_conversion(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    monkeypatch.setattr("app.main.repair_pdf", lambda source, dest: dest.write_bytes(source.read_bytes()))
    converted_pdf = b"%PDF-1.4 converted"

    call_count = {"count": 0}

    def fake_inspect(data: bytes, password: str | None = None):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise ValueError("409_XFA_NOT_CONVERTIBLE")
        return {
            "fields": [{"name": "converted_field", "type": "text", "page": 1, "bbox": [0, 0, 100, 20]}],
            "pageCount": 1,
            "hasXfa": True,
            "xfaConvertible": True,
            "warnings": [],
        }

    monkeypatch.setattr("app.main.inspect_pdf", fake_inspect)
    monkeypatch.setattr("app.main.convert_xfa_to_acroform", lambda data, password=None: converted_pdf)

    response = client.post("/v1/inspect", files={"file": ("xfa.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert body["fields"][0]["name"] == "converted_field"
    assert any("XFA was converted" in warning for warning in body["warnings"])


def test_batch_returns_zip_artifact(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    monkeypatch.setattr("app.main.fill_pdf", lambda **kwargs: Path(kwargs["dest"]).write_bytes(b"%PDF-1.4 filled"))

    pdf_zip = io.BytesIO()
    with zipfile.ZipFile(pdf_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample.pdf", b"%PDF-1.4")

    response = client.post(
        "/v1/batch",
        files={
            "pdf_zip": ("inputs.zip", pdf_zip.getvalue(), "application/zip"),
            "csv_mapping": ("map.csv", b"source,name\nsample.pdf,Ada\n", "text/csv"),
        },
        data={"regenerate_appearance": "true", "flatten": "false"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["requested"] == 1


def test_batch_handles_missing_sources_and_large_rows(monkeypatch, tmp_path: Path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    monkeypatch.setattr("app.main.fill_pdf", lambda **kwargs: Path(kwargs["dest"]).write_bytes(b"%PDF-1.4 filled"))

    pdf_zip = io.BytesIO()
    with zipfile.ZipFile(pdf_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("forms/a.pdf", b"%PDF-1.4")

    rows = ["source,name"]
    for idx in range(1, 101):
        source = "forms/a.pdf" if idx % 2 == 0 else f"missing-{idx}.pdf"
        rows.append(f"{source},User {idx}")
    csv_bytes = ("\n".join(rows) + "\n").encode("utf-8")

    response = client.post(
        "/v1/batch",
        files={
            "pdf_zip": ("inputs.zip", pdf_zip.getvalue(), "application/zip"),
            "csv_mapping": ("map.csv", csv_bytes, "text/csv"),
        },
        data={"regenerate_appearance": "true", "flatten": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 100
    assert body["count"] == 50
    assert len(body["skipped"]) == 50
