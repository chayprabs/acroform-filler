from __future__ import annotations

import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import settings
from .import_parsers import create_batch_zip, parse_csv_mapping, parse_import_file
from .inspect import inspect_pdf
from .jobs import JobRecord, job_store
from .pdf_tools import fill_pdf, repair_pdf
from .validate import validate_values
from .xfa import convert_xfa_to_acroform

SAMPLE_FILENAMES = {
    "w9": "w9.pdf",
    "i9": "i9.pdf",
    "registration": "registration.pdf",
    "multi-page": "multi-page.pdf",
}

ERROR_MESSAGES: dict[str, str] = {
    "400_PDF_INVALID": "The uploaded PDF could not be parsed.",
    "401_PDF_PASSWORD_REQUIRED": "This PDF is encrypted and requires a valid password.",
    "409_XFA_NOT_CONVERTIBLE": "This PDF is XFA-only and could not be converted to AcroForm.",
    "422_FIELD_VALUE_INVALID": "One or more field values are invalid.",
}

STATUS_BY_CODE = {
    "400_PDF_INVALID": 400,
    "401_PDF_PASSWORD_REQUIRED": 401,
    "409_XFA_NOT_CONVERTIBLE": 409,
    "422_FIELD_VALUE_INVALID": 422,
}


class FillRequest(BaseModel):
    jobId: str
    values: dict[str, Any] = Field(default_factory=dict)
    regenerateAppearance: bool = True
    flatten: bool = False


class ValidateRequest(BaseModel):
    jobId: str
    values: dict[str, Any] = Field(default_factory=dict)


def _error_payload(code: str) -> dict[str, str]:
    return {"code": code, "message": ERROR_MESSAGES.get(code, "Unexpected error.")}


def _raise_code(code: str) -> None:
    raise HTTPException(status_code=STATUS_BY_CODE.get(code, 500), detail=_error_payload(code))


def _normalize_values(values: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, raw in values.items():
        if raw is None:
            normalized[key] = ""
        elif isinstance(raw, bool):
            normalized[key] = "Yes" if raw else "Off"
        else:
            normalized[key] = str(raw)
    return normalized


def _normalize_source_name(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _get_job_or_404(job_id: str) -> JobRecord:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "404_JOB_NOT_FOUND", "message": "Job not found."})
    if not job.source_pdf or not job.source_pdf.exists():
        raise HTTPException(status_code=404, detail={"code": "404_SOURCE_NOT_FOUND", "message": "Source PDF not found."})
    if not job.fields:
        job_store.load_metadata(job)
    return job


def _artifact_response(job: JobRecord, artifact_name: str, filename: str) -> dict[str, str]:
    artifact_id = artifact_name
    expires_at = int(time.time()) + settings.job_ttl_seconds
    token = job_store.sign_artifact(artifact_id=artifact_id, job_id=job.job_id, expires_at=expires_at)
    return {
        "artifactId": artifact_id,
        "filename": filename,
        "downloadUrl": f"/v1/artifacts/{artifact_id}?jobId={job.job_id}&expiresAt={expires_at}&token={token}",
        "expiresAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires_at)),
    }


app = FastAPI(title="PdfForms Worker", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/samples")
def list_samples() -> dict[str, list[dict[str, str]]]:
    samples = [{"id": key, "filename": value} for key, value in SAMPLE_FILENAMES.items()]
    return {"samples": samples}


@app.get("/v1/samples/{sample_id}")
def get_sample(sample_id: str) -> FileResponse:
    filename = SAMPLE_FILENAMES.get(sample_id)
    if not filename:
        raise HTTPException(status_code=404, detail={"code": "404_SAMPLE_NOT_FOUND", "message": "Sample not found."})
    sample_path = Path(settings.samples_dir) / filename
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail={"code": "404_SAMPLE_NOT_FOUND", "message": "Sample not found."})
    return FileResponse(sample_path, media_type="application/pdf", filename=filename)


@app.post("/v1/inspect")
async def inspect_endpoint(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
) -> JSONResponse:
    payload = await file.read()
    if not payload:
        _raise_code("400_PDF_INVALID")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail={"code": "413_UPLOAD_TOO_LARGE", "message": "Upload exceeds limit."})

    job = job_store.create()
    source_path = job_store.artifact_path(job, "source.pdf")
    source_path.write_bytes(payload)
    inspect_target = source_path
    inspect_payload = payload

    try:
        result = inspect_pdf(inspect_payload, password=password)
    except ValueError as exc:
        code = str(exc)
        if code == "400_PDF_INVALID":
            repaired_path = job_store.artifact_path(job, "repaired.pdf")
            try:
                repair_pdf(source_path, repaired_path)
            except RuntimeError:
                _raise_code(code)
            inspect_target = repaired_path
            inspect_payload = repaired_path.read_bytes()
            try:
                result = inspect_pdf(inspect_payload, password=password)
                code = ""
            except ValueError as repaired_exc:
                code = str(repaired_exc)
        if code == "409_XFA_NOT_CONVERTIBLE":
            converted = convert_xfa_to_acroform(inspect_payload, password=password)
            if converted:
                converted_path = job_store.artifact_path(job, "xfa-converted.pdf")
                converted_path.write_bytes(converted)
                try:
                    result = inspect_pdf(converted, password=password)
                    result["warnings"].append("XFA was converted to AcroForm using sidecar conversion.")
                    inspect_target = converted_path
                except ValueError:
                    _raise_code(code)
            else:
                _raise_code(code)
        elif code:
            _raise_code(code)

    job.source_pdf = inspect_target
    job.fields = result["fields"]
    job.page_count = result["pageCount"]
    job.has_xfa = result["hasXfa"]
    job.xfa_convertible = result["xfaConvertible"]
    job.warnings = result["warnings"]
    job_store.save_metadata(job)

    body = {"jobId": job.job_id, **result}
    return JSONResponse(content=body)


@app.post("/v1/import")
async def import_endpoint(file: UploadFile = File(...)) -> dict[str, dict[str, str]]:
    payload = await file.read()
    try:
        values = parse_import_file(file.filename or "", payload)
    except ValueError as exc:
        _raise_code(str(exc))
    return {"values": values}


@app.post("/v1/validate")
def validate_endpoint(request: ValidateRequest) -> dict[str, Any]:
    job = _get_job_or_404(request.jobId)
    issues = validate_values(job.fields, request.values)
    return {"valid": not issues, "issues": issues}


@app.post("/v1/fill")
def fill_endpoint(request: FillRequest) -> dict[str, Any]:
    job = _get_job_or_404(request.jobId)
    issues = validate_values(job.fields, request.values)
    warnings: list[str] = []
    if request.flatten:
        missing_required = [issue for issue in issues if issue["code"] == "REQUIRED_MISSING"]
        if missing_required:
            warnings.append("Flatten requested with missing required fields.")

    output_name = f"filled-{int(time.time())}.pdf"
    output_path = job_store.artifact_path(job, output_name)
    try:
        fill_pdf(
            source=job.source_pdf,
            dest=output_path,
            values=_normalize_values(request.values),
            regenerate_appearance=request.regenerateAppearance,
            flatten=request.flatten,
        )
    except RuntimeError:
        _raise_code("422_FIELD_VALUE_INVALID")

    artifact = _artifact_response(job, artifact_name=output_name, filename="filled.pdf")
    return {"artifact": artifact, "issues": issues, "warnings": warnings}


@app.post("/v1/batch")
async def batch_endpoint(
    pdf_zip: UploadFile = File(...),
    csv_mapping: UploadFile = File(...),
    regenerate_appearance: bool = Form(default=True),
    flatten: bool = Form(default=False),
) -> dict[str, Any]:
    csv_rows = parse_csv_mapping(await csv_mapping.read())
    if len(csv_rows) > settings.max_batch_files:
        raise HTTPException(status_code=413, detail={"code": "413_BATCH_TOO_LARGE", "message": "Batch exceeds max files."})

    zip_bytes = await pdf_zip.read()
    job = job_store.create()
    output_pairs: list[tuple[str, Path]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        pdf_names = {_normalize_source_name(item.filename) for item in archive.infolist() if item.filename.lower().endswith(".pdf")}
        for row_index, row in enumerate(csv_rows, start=1):
            source_name = _normalize_source_name((row.get("source") or "").strip())
            if not source_name:
                skipped.append({"reason": "missing_source", "source": ""})
                continue
            if source_name not in pdf_names:
                skipped.append({"reason": "source_not_found", "source": source_name})
                continue
            row_values = {key: value for key, value in row.items() if key != "source"}
            source_bytes = archive.read(source_name)
            source_path = job_store.artifact_path(job, f"batch-{Path(source_name).name}")
            source_path.write_bytes(source_bytes)
            stem = Path(source_name).stem
            suffix = Path(source_name).suffix or ".pdf"
            filled_name = f"filled-{row_index:03d}-{stem}{suffix}"
            filled_path = job_store.artifact_path(job, filled_name)
            try:
                fill_pdf(
                    source=source_path,
                    dest=filled_path,
                    values=_normalize_values(row_values),
                    regenerate_appearance=regenerate_appearance,
                    flatten=flatten,
                )
            except RuntimeError:
                errors.append({"source": source_name, "code": "422_FIELD_VALUE_INVALID"})
                continue
            output_pairs.append((filled_name, filled_path))

    artifact_name = f"batch-{int(time.time())}.zip"
    artifact_path = job_store.artifact_path(job, artifact_name)
    artifact_path.write_bytes(create_batch_zip(output_pairs))
    artifact = _artifact_response(job, artifact_name=artifact_name, filename="filled-batch.zip")
    return {
        "artifact": artifact,
        "count": len(output_pairs),
        "requested": len(csv_rows),
        "skipped": skipped,
        "errors": errors,
    }


@app.get("/v1/artifacts/{artifact_id}")
def download_artifact(
    artifact_id: str,
    jobId: str = Query(...),
    expiresAt: int = Query(...),
    token: str = Query(...),
) -> FileResponse:
    job = job_store.get(jobId)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "404_JOB_NOT_FOUND", "message": "Job not found."})
    if not job_store.verify_artifact(artifact_id=artifact_id, job_id=jobId, expires_at=expiresAt, token=token):
        raise HTTPException(status_code=403, detail={"code": "403_BAD_TOKEN", "message": "Invalid or expired token."})
    artifact_path = job_store.artifact_path(job, artifact_id)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail={"code": "404_ARTIFACT_NOT_FOUND", "message": "Artifact not found."})
    media_type = "application/zip" if artifact_path.suffix == ".zip" else "application/pdf"
    return FileResponse(path=artifact_path, media_type=media_type, filename=artifact_path.name)
