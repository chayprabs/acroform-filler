from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="chayprabs/acroform-filler")
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--trigger-release", action="store_true")
    parser.add_argument("--ref", default="cursor/pdf-forms-build")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    commands = [
        ["gh", "variable", "set", "PDF_FORMS_WEB_URL", "--body", args.web_url, "-R", args.repo],
        ["gh", "variable", "set", "PDF_FORMS_API_URL", "--body", args.api_url, "-R", args.repo],
    ]
    if args.trigger_release:
        commands.append(
            [
                "gh",
                "workflow",
                "run",
                "Release",
                "-R",
                args.repo,
                "--ref",
                args.ref,
                "-f",
                f"web_url={args.web_url}",
                "-f",
                f"api_url={args.api_url}",
            ]
        )

    if args.dry_run:
        print(json.dumps({"ok": True, "dryRun": True, "commands": [" ".join(shlex.quote(c) for c in cmd) for cmd in commands]}, indent=2))
        raise SystemExit(0)

    failures: list[dict[str, object]] = []
    for cmd in commands:
        code, out, err = _run(cmd)
        if code != 0:
            failures.append({"command": cmd, "exitCode": code, "stderrTail": err[-600:], "stdoutTail": out[-300:]})

    report = {"ok": len(failures) == 0, "failures": failures}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
