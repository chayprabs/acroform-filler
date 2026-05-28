from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.jobs import JobStore
from app.main import app


def _fill_values(fields: list[dict[str, object]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in fields:
        field_name = str(field["name"])
        field_type = str(field["type"])
        if field_type in {"text", "combo", "listbox"}:
            values[field_name] = "PdfForms Snapshot"
        elif field_type == "checkbox":
            values[field_name] = "Yes"
    return values


def _download_artifact(client: TestClient, download_url: str) -> bytes:
    parsed = urlparse(download_url)
    query = parse_qs(parsed.query)
    response = client.get(
        parsed.path,
        params={
            "jobId": query["jobId"][0],
            "expiresAt": query["expiresAt"][0],
            "token": query["token"][0],
        },
    )
    response.raise_for_status()
    return response.content


def _client_with_tmp_store(monkeypatch, tmp_path: Path) -> TestClient:
    store = JobStore(root=tmp_path / "jobs")
    monkeypatch.setattr("app.main.job_store", store)
    return TestClient(app)


def test_w9_and_i9_fill_flatten_snapshots_download_nontrivial_artifacts(monkeypatch, tmp_path) -> None:
    client = _client_with_tmp_store(monkeypatch, tmp_path)
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    sample_names = ["w9.pdf", "i9.pdf"]

    for sample_name in sample_names:
        sample = (samples_dir / sample_name).read_bytes()
        inspect = client.post("/v1/inspect", files={"file": (sample_name, sample, "application/pdf")})
        assert inspect.status_code == 200

        body = inspect.json()
        values = _fill_values(body["fields"])
        fill = client.post(
            "/v1/fill",
            json={
                "jobId": body["jobId"],
                "values": values,
                "regenerateAppearance": True,
                "flatten": True,
            },
        )
        fill.raise_for_status()

        artifact = _download_artifact(client, fill.json()["artifact"]["downloadUrl"])
        assert len(artifact) > 10_000
