from __future__ import annotations

import argparse
import json
import os
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
        return json.loads(audit_path.read_text(encoding="utf-8")), "existing"
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


def _check_hosted(repo_root: Path) -> dict[str, object]:
    code, out, _ = _run(
        [sys.executable, "apps/worker/scripts/verify_hosted.py", "--allow-missing", "--derive-api-from-web"],
        repo_root,
    )
    payload = json.loads(out)
    return {"ok": code == 0 and bool(payload.get("ok")), "payload": payload}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="chayprabs/acroform-filler")
    parser.add_argument("--tag", default="v0.1.0-rc.3")
    parser.add_argument("--output", default="apps/worker/artifacts/section14/section14-report.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    local_audit, local_source = _load_or_run_local_audit(repo_root)
    release = _check_release(repo_root, args.repo, args.tag)
    hosted = _check_hosted(repo_root)

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
    checks.append(
        {
            "id": "14.20.A1.preview",
            "status": "pass" if preview_shot.exists() else "blocked",
            "evidence": str(preview_shot) if preview_shot.exists() else "missing macOS Preview screenshot",
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

    report = {
        "tool": "PdfForms",
        "section": "14",
        "repo": args.repo,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "checks": checks,
        "verdict": verdict,
    }

    out_path = (repo_root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
