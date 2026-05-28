from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _run(command: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _load_or_run_local_audit(repo_root: Path) -> tuple[dict[str, object], str]:
    audit_path = repo_root / "apps/worker/artifacts/section14/local-audit.json"
    if audit_path.exists():
        existing = json.loads(audit_path.read_text(encoding="utf-8"))
        if bool(existing.get("ok")):
            return existing, "existing"
    code, out, _ = _run(
        [sys.executable, "apps/worker/scripts/run_section14_local.py", "--skip-hosted"],
        repo_root,
    )
    payload = json.loads(out)
    if code != 0:
        raise RuntimeError("run_section14_local.py failed")
    return payload, "fresh"


def _check_release(repo_root: Path, repo: str, tag: str) -> dict[str, object]:
    code, out, _ = _run(
        [sys.executable, "apps/worker/scripts/verify_release_artifacts.py", "--repo", repo, "--tag", tag],
        repo_root,
    )
    payload = json.loads(out)
    return {"ok": code == 0 and bool(payload.get("ok")), "payload": payload}


def _check_hosted(
    repo_root: Path,
    web_url: str | None,
    api_url: str | None,
    allow_missing: bool,
) -> dict[str, object]:
    command = [sys.executable, "apps/worker/scripts/verify_hosted.py", "--derive-api-from-web"]
    if allow_missing:
        command.append("--allow-missing")
    if web_url:
        command.extend(["--web-url", web_url])
    if api_url:
        command.extend(["--api-url", api_url])
    code, out, _ = _run(command, repo_root)
    payload = json.loads(out)
    return {"ok": code == 0 and bool(payload.get("ok")), "payload": payload}


def _ingest_preview_screenshot(repo_root: Path, screenshot: str | None) -> None:
    if not screenshot:
        return
    command = [
        sys.executable,
        "apps/worker/scripts/record_preview_evidence.py",
        "--screenshot",
        screenshot,
    ]
    code, _, _ = _run(command, repo_root)
    if code != 0:
        raise RuntimeError("record_preview_evidence.py failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="chayprabs/acroform-filler")
    parser.add_argument("--tag", default="v0.1.0-rc.3")
    parser.add_argument("--output", default="apps/worker/artifacts/section14/section14-report.json")
    parser.add_argument("--web-url", help="Hosted web URL override for Section 14 verification")
    parser.add_argument("--api-url", help="Hosted API URL override for Section 14 verification")
    parser.add_argument("--preview-screenshot", help="Path to macOS Preview screenshot to ingest before verdict")
    parser.add_argument("--strict-hosted", action="store_true", help="Fail instead of verify-deferred when hosted URLs are missing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    _ingest_preview_screenshot(repo_root, args.preview_screenshot)
    local_audit, local_source = _load_or_run_local_audit(repo_root)
    release = _check_release(repo_root, args.repo, args.tag)
    hosted = _check_hosted(
        repo_root=repo_root,
        web_url=args.web_url,
        api_url=args.api_url,
        allow_missing=not args.strict_hosted,
    )

    checks: list[dict[str, object]] = []
    checks.append({"id": "14.local_automation", "status": "pass" if local_audit.get("ok") else "fail", "evidence": local_source})
    checks.append({"id": "14.17.release_artifacts", "status": "pass" if release["ok"] else "fail", "evidence": release["payload"]})

    hosted_payload = hosted["payload"]
    hosted_skipped = isinstance(hosted_payload, dict) and bool(hosted_payload.get("skipped"))
    if hosted_skipped:
        checks.append({"id": "14.17.hosted_urls", "status": "verify-deferred", "evidence": hosted_payload})
    else:
        checks.append({"id": "14.17.hosted_urls", "status": "pass" if hosted["ok"] else "fail", "evidence": hosted_payload})

    preview_shot = repo_root / "docs/screenshots/a1-preview-macos.png"
    preview_manifest = repo_root / "apps/worker/artifacts/a1-evidence/preview-evidence.json"
    manifest_payload: dict[str, object] | None = None
    if preview_manifest.exists():
        try:
            manifest_payload = json.loads(preview_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest_payload = {"ok": False, "reason": "invalid preview manifest JSON"}
    checks.append(
        {
            "id": "14.20.A1.preview",
            "status": "pass" if preview_shot.exists() else "blocked",
            "evidence": manifest_payload if manifest_payload is not None else (str(preview_shot) if preview_shot.exists() else "missing macOS Preview screenshot"),
        }
    )

    counts = {"pass": 0, "fail": 0, "blocked": 0, "verify-deferred": 0}
    for check in checks:
        status = str(check["status"])
        counts[status] = counts.get(status, 0) + 1

    verdict = "QUALIFIED"
    if counts["fail"] > 0 or counts["blocked"] > 0:
        verdict = "NOT QUALIFIED"
    elif counts["verify-deferred"] > 0:
        verdict = "VERIFY-DEFERRED"

    remaining_actions: list[str] = []
    if checks[2]["status"] != "pass":
        remaining_actions.append("Set PDF_FORMS_WEB_URL and PDF_FORMS_API_URL (or pass --web-url/--api-url) and rerun section14_report.py.")
    if checks[3]["status"] != "pass":
        remaining_actions.append("Capture macOS Preview screenshot and pass --preview-screenshot to section14_report.py.")

    report = {
        "tool": "PdfForms",
        "section": "14",
        "repo": args.repo,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "checks": checks,
        "verdict": verdict,
        "remainingActions": remaining_actions,
    }

    out_path = (repo_root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
