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

    monkeypatch.setattr("app.main.repair_pdf", lambda source, dest: dest.write_bytes(source.read_bytes()))

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
