from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="chayprabs/acroform-filler")
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="cursor/pdf-forms-build")
    parser.add_argument(
        "--report-path",
        default="apps/worker/artifacts/section14/section14-report.json",
        help="Path to section14_report.py output",
    )
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        print(json.dumps({"ok": False, "reason": f"Report not found: {report_path}"}, indent=2))
        raise SystemExit(2)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    verdict = report.get("verdict")
    if verdict != "QUALIFIED":
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "Section 14 is not qualified yet; PR creation is gated.",
                    "verdict": verdict,
                    "counts": report.get("counts"),
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    title = "PdfForms: v1 build (QC Section 14 qualified)"
    body = (
        "Qualifying-Criteria-PASS: pdf-forms\n\n"
        "Automated evidence:\n"
        f"- Section 14 report: `{report_path}`\n"
        f"- Counts: `{json.dumps(report.get('counts', {}), separators=(',', ':'))}`\n"
    )

    cmd = [
        "gh",
        "pr",
        "create",
        "-R",
        args.repo,
        "--base",
        args.base,
        "--head",
        args.head,
        "--title",
        title,
        "--body",
        body,
    ]
    if args.draft:
        cmd.append("--draft")

    code, out, err = _run(cmd)
    if code != 0:
        print(json.dumps({"ok": False, "reason": "gh pr create failed", "stderrTail": err[-800:]}, indent=2))
        raise SystemExit(code)

    print(json.dumps({"ok": True, "prUrl": out.strip()}, indent=2))
