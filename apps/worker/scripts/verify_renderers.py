from __future__ import annotations

import json
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app


def _generate_filled_pdf(tmp_dir: Path) -> Path:
    client = TestClient(app)
    sample_path = Path(__file__).resolve().parents[1] / "samples" / "w9.pdf"
    sample = sample_path.read_bytes()
    inspect = client.post("/v1/inspect", files={"file": ("w9.pdf", sample, "application/pdf")})
    inspect.raise_for_status()
    body = inspect.json()
    values = {}
    for field in body["fields"][:10]:
        field_type = field["type"]
        if field_type in {"text", "combo", "listbox"}:
            values[field["name"]] = "PdfForms QA"
        elif field_type == "checkbox":
            values[field["name"]] = "Yes"

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
    url = fill.json()["artifact"]["downloadUrl"]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    downloaded = client.get(
        parsed.path,
        params={"jobId": query["jobId"][0], "expiresAt": query["expiresAt"][0], "token": query["token"][0]},
    )
    downloaded.raise_for_status()
    output = tmp_dir / "filled-w9.pdf"
    output.write_bytes(downloaded.content)
    return output


def _verify_pdfjs(pdf_path: Path) -> dict[str, object]:
    script = Path(__file__).resolve().parents[2] / "web" / "scripts" / "verify_pdfjs_render.mjs"
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["pnpm.cmd", "exec", "node", str(script), str(pdf_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, object]
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "parseError": result.stdout[-300:]}
    payload["exitCode"] = result.returncode
    payload["ok"] = bool(payload.get("ok")) and result.returncode == 0
    return payload


def _verify_mutool(pdf_path: Path) -> dict[str, object]:
    mutool = shutil.which("mutool")
    if not mutool:
        return {"ok": False, "available": False, "reason": "mutool not installed on host"}
    out = subprocess.run(
        [mutool, "draw", "-F", "txt", "-o", "-", str(pdf_path), "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = out.stdout or ""
    return {
        "ok": out.returncode == 0 and len(text) > 40,
        "available": True,
        "exitCode": out.returncode,
        "containsMarker": "PdfForms QA" in text,
        "textLength": len(text),
    }


def _verify_chrome_viewer(pdf_path: Path) -> dict[str, object]:
    script = Path(__file__).resolve().parents[2] / "web" / "scripts" / "verify_chrome_pdf_viewer.mjs"
    repo_root = Path(__file__).resolve().parents[3]
    pnpm_cmd = "pnpm.cmd" if os.name == "nt" else "pnpm"
    command = [pnpm_cmd, "exec", "node", str(script), str(pdf_path), "--headed"]
    xvfb = shutil.which("xvfb-run")
    if xvfb:
        command = [xvfb, "-a", *command]

    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload: dict[str, object]
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "parseError": result.stdout[-300:]}
    payload["exitCode"] = result.returncode
    payload["stderrTail"] = (result.stderr or "")[-300:]
    payload["ok"] = bool(payload.get("ok")) and result.returncode == 0
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pdfjs", action="store_true")
    parser.add_argument("--skip-mutool", action="store_true")
    parser.add_argument("--skip-chrome", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pdf-forms-render-") as raw_tmp:
        tmp_dir = Path(raw_tmp)
        pdf = _generate_filled_pdf(tmp_dir)
        report = {
            "pdfPath": str(pdf),
            "pdfjs": {"skipped": True} if args.skip_pdfjs else _verify_pdfjs(pdf),
            "mutool": {"skipped": True} if args.skip_mutool else _verify_mutool(pdf),
            "chromeViewer": {"skipped": True} if args.skip_chrome else _verify_chrome_viewer(pdf),
        }
        print(json.dumps(report, indent=2))
        failed = []
        for key in ("pdfjs", "mutool", "chromeViewer"):
            section = report.get(key, {})
            if isinstance(section, dict) and not section.get("skipped") and not section.get("ok"):
                failed.append(key)
        if failed:
            print(f"Renderer verification failed for: {', '.join(failed)}", file=sys.stderr)
            sys.exit(1)
