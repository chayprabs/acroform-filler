from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _pnpm_cmd() -> str:
    return "pnpm.cmd" if os.name == "nt" else "pnpm"


def _extract_json_blob(text: str) -> dict[str, object] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    blob = text[start : end + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _run_step(name: str, command: list[str], cwd: Path) -> dict[str, object]:
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    payload = _extract_json_blob(proc.stdout)
    return {
        "name": name,
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "command": " ".join(command),
        "cwd": str(cwd),
        "json": payload,
        "stdoutTail": (proc.stdout or "")[-1500:],
        "stderrTail": (proc.stderr or "")[-800:],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="apps/worker/artifacts/section14/local-audit.json")
    parser.add_argument("--skip-seo-e2e", action="store_true")
    parser.add_argument("--skip-hosted", action="store_true")
    parser.add_argument("--skip-mutool-if-missing", action="store_true", default=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    worker_dir = repo_root / "apps" / "worker"

    steps: list[dict[str, object]] = []
    steps.append(_run_step("pytest", [sys.executable, "-m", "pytest"], worker_dir))
    steps.append(
        _run_step(
            "p95",
            [
                sys.executable,
                "scripts/measure_p95.py",
                "--sample",
                "samples/w9.pdf",
                "--iterations",
                "10",
                "--max-inspect-ms",
                "2000",
                "--max-fill-ms",
                "5000",
            ],
            worker_dir,
        )
    )
    steps.append(_run_step("acceptance", [sys.executable, "scripts/run_acceptance.py"], worker_dir))
    renderer_command = [sys.executable, "scripts/verify_renderers.py"]
    if args.skip_mutool_if_missing and shutil.which("mutool") is None:
        renderer_command.append("--skip-mutool")
    steps.append(_run_step("renderers", renderer_command, worker_dir))

    if args.skip_seo_e2e:
        steps.append({"name": "seo_e2e", "ok": True, "skipped": True})
    else:
        steps.append(
            _run_step(
                "seo_e2e",
                [_pnpm_cmd(), "--filter", "@pdf-forms/web", "test:e2e", "--", "tests/e2e/seo-routes.spec.ts"],
                repo_root,
            )
        )

    if args.skip_hosted:
        steps.append({"name": "hosted", "ok": True, "skipped": True})
    else:
        steps.append(
            _run_step(
                "hosted",
                [sys.executable, "apps/worker/scripts/verify_hosted.py", "--allow-missing", "--derive-api-from-web"],
                repo_root,
            )
        )

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "repoRoot": str(repo_root),
        "steps": steps,
    }
    report["ok"] = all(bool(step.get("ok")) for step in steps)

    out_path = (repo_root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
