from __future__ import annotations

import logging
from pathlib import Path

from app.import_parsers import RedactingFilter
from app.jobs import JobStore


def test_redacting_filter_masks_password_tokens() -> None:
    record = logging.LogRecord(
        name="pdf-forms",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg='inspect payload password=supersecret pwd:"abc123" passwd:zzz',
        args=(),
        exc_info=None,
    )
    filt = RedactingFilter()
    assert filt.filter(record) is True
    assert "supersecret" not in record.msg
    assert "abc123" not in record.msg
    assert "zzz" not in record.msg
    assert "[REDACTED]" in record.msg


def test_job_metadata_excludes_password_field(tmp_path: Path) -> None:
    store = JobStore(root=tmp_path / "jobs")
    job = store.create()
    job.fields = [{"name": "field1", "type": "text"}]
    job.page_count = 1
    store.save_metadata(job)
    saved = (job.directory / "metadata.json").read_text(encoding="utf-8")
    assert "password" not in saved.lower()
