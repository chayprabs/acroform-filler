from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app


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


def _fill_w9_pdf(out_dir: Path) -> Path:
    client = TestClient(app)
    sample_path = Path(__file__).resolve().parents[1] / "samples" / "w9.pdf"
    sample = sample_path.read_bytes()
    inspect = client.post("/v1/inspect", files={"file": ("w9.pdf", sample, "application/pdf")})
    inspect.raise_for_status()
    body = inspect.json()
    values: dict[str, str] = {}
    for field in body["fields"][:10]:
        field_name = field["name"]
        field_type = field["type"]
        if field_type in {"text", "combo", "listbox"}:
            values[field_name] = "PdfForms QA"
        elif field_type == "checkbox":
            values[field_name] = "Yes"
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
    pdf_bytes = _download_artifact(client, fill.json()["artifact"]["downloadUrl"])
    out_pdf = out_dir / "a1-filled-w9.pdf"
    out_pdf.write_bytes(pdf_bytes)
    return out_pdf


def _run_json_cmd(command: list[str], cwd: Path | None = None) -> dict[str, object]:
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd, check=False)
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "parseError": (result.stdout or "")[-300:]}
    payload["exitCode"] = result.returncode
    payload["stderrTail"] = (result.stderr or "")[-300:]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="apps/worker/artifacts/a1-evidence")
    parser.add_argument("--skip-mutool", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = (repo_root / args.out_dir).resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    filled_pdf = _fill_w9_pdf(out_dir)
    pdfjs = _run_json_cmd(
        ["pnpm.cmd" if os.name == "nt" else "pnpm", "exec", "node", "apps/web/scripts/verify_pdfjs_render.mjs", str(filled_pdf)],
        cwd=repo_root,
    )
    chrome = _run_json_cmd(
        [
            "pnpm.cmd" if os.name == "nt" else "pnpm",
            "exec",
            "node",
            "apps/web/scripts/verify_chrome_pdf_viewer.mjs",
            str(filled_pdf),
            "--headed",
        ],
        cwd=repo_root,
    )

    mutool = shutil.which("mutool")
    if args.skip_mutool:
        mutool_payload = {"ok": True, "skipped": True}
    elif mutool:
        mutool_run = subprocess.run(
            [mutool, "draw", "-F", "txt", "-o", "-", str(filled_pdf), "1"],
            capture_output=True,
            text=True,
            check=False,
        )
        mutool_payload: dict[str, object] = {
            "ok": mutool_run.returncode == 0 and len(mutool_run.stdout or "") > 40,
            "exitCode": mutool_run.returncode,
            "textLength": len(mutool_run.stdout or ""),
            "containsMarker": "PdfForms QA" in (mutool_run.stdout or ""),
        }
    else:
        mutool_payload = {"ok": False, "reason": "mutool not installed"}

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "filledPdf": str(filled_pdf),
        "pdfjs": pdfjs,
        "chromeViewer": chrome,
        "mutool": mutool_payload,
        "previewManualStep": "Open a1-filled-w9.pdf in macOS Preview and confirm visible values, then attach screenshot.",
    }
    report["ok"] = bool(pdfjs.get("ok")) and bool(chrome.get("ok")) and bool(mutool_payload.get("ok"))
    (out_dir / "a1-evidence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
