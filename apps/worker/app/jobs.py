from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import settings


@dataclass
class JobRecord:
    job_id: str
    directory: Path
    created_at: float = field(default_factory=time.time)
    source_pdf: Path | None = None
    fields: list[dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    has_xfa: bool = False
    xfa_convertible: bool = False
    warnings: list[str] = field(default_factory=list)


class JobStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("/tmp/pdf-forms-jobs")
        self.root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, JobRecord] = {}

    def create(self) -> JobRecord:
        job_id = uuid.uuid4().hex
        directory = self.root / job_id
        directory.mkdir(parents=True, exist_ok=True)
        record = JobRecord(job_id=job_id, directory=directory)
        self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        self._purge_expired()
        return self._jobs.get(job_id)

    def _purge_expired(self) -> None:
        cutoff = time.time() - settings.job_ttl_seconds
        expired = [job_id for job_id, job in self._jobs.items() if job.created_at < cutoff]
        for job_id in expired:
            job = self._jobs.pop(job_id, None)
            if job and job.directory.exists():
                shutil.rmtree(job.directory, ignore_errors=True)

    def sign_artifact(self, artifact_id: str, job_id: str, expires_at: int) -> str:
        payload = f"{artifact_id}:{job_id}:{expires_at}"
        return hmac.new(
            settings.artifact_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_artifact(self, artifact_id: str, job_id: str, expires_at: int, token: str) -> bool:
        if expires_at < int(time.time()):
            return False
        expected = self.sign_artifact(artifact_id, job_id, expires_at)
        return hmac.compare_digest(expected, token)

    def artifact_path(self, job: JobRecord, name: str) -> Path:
        return job.directory / name

    def save_metadata(self, job: JobRecord) -> None:
        meta = {
            "jobId": job.job_id,
            "fields": job.fields,
            "pageCount": job.page_count,
            "hasXfa": job.has_xfa,
            "xfaConvertible": job.xfa_convertible,
            "warnings": job.warnings,
        }
        (job.directory / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

    def load_metadata(self, job: JobRecord) -> None:
        meta_path = job.directory / "metadata.json"
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        job.fields = meta.get("fields", [])
        job.page_count = meta.get("pageCount", 0)
        job.has_xfa = meta.get("hasXfa", False)
        job.xfa_convertible = meta.get("xfaConvertible", False)
        job.warnings = meta.get("warnings", [])


job_store = JobStore()
