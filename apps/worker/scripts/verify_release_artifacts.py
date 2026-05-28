from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _gh_json(args: list[str]) -> dict | list:
    cmd = ["gh", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh command failed")
    return json.loads(result.stdout)


def _workflow_ok(repo: str, tag: str) -> dict[str, object]:
    try:
        runs = _gh_json(["api", f"repos/{repo}/actions/runs?event=push&per_page=100"])
    except RuntimeError as exc:
        return {"ok": False, "reason": str(exc)}
    wanted_ref = f"refs/tags/{tag}"
    for run in runs.get("workflow_runs", []):
        if run.get("name") == "Release" and run.get("head_branch") == tag and run.get("status") == "completed":
            return {
                "ok": run.get("conclusion") == "success",
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url"),
                "id": run.get("id"),
            }
        if run.get("name") == "Release" and run.get("head_branch") is None and run.get("display_title", "").startswith(tag):
            if run.get("status") == "completed":
                return {
                    "ok": run.get("conclusion") == "success",
                    "conclusion": run.get("conclusion"),
                    "url": run.get("html_url"),
                    "id": run.get("id"),
                }
        if run.get("name") == "Release" and run.get("head_branch") == wanted_ref and run.get("status") == "completed":
            return {
                "ok": run.get("conclusion") == "success",
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url"),
                "id": run.get("id"),
            }
    return {"ok": False, "reason": f"No completed Release workflow run found for tag {tag}"}


def _package_has_tag(owner: str, package_name: str, tag: str) -> dict[str, object]:
    try:
        versions = _gh_json(
            [
                "api",
                f"/users/{owner}/packages/container/{package_name}/versions?per_page=100",
            ]
        )
    except RuntimeError as exc:
        reason = str(exc)
        if "read:packages" in reason or "HTTP 403" in reason:
            image_ref = f"ghcr.io/{owner}/{package_name}:{tag}"
            manifest = subprocess.run(
                ["docker", "manifest", "inspect", image_ref],
                capture_output=True,
                text=True,
                check=False,
            )
            if manifest.returncode == 0:
                return {"ok": True, "source": "docker-manifest", "image": image_ref}
            return {"ok": False, "reason": reason, "dockerReason": (manifest.stderr or "").strip()[-300:]}
        return {"ok": False, "reason": reason}
    for version in versions:
        tags = (version.get("metadata") or {}).get("container", {}).get("tags", [])
        if tag in tags:
            return {"ok": True, "versionId": version.get("id"), "tags": tags}
    return {"ok": False, "reason": f"Tag {tag} not found in GHCR package {package_name}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/repo (e.g. chayprabs/acroform-filler)")
    parser.add_argument("--tag", required=True, help="release tag (e.g. v1.0.0)")
    args = parser.parse_args()

    owner, _ = args.repo.split("/", 1)
    worker_pkg = "acroform-filler-worker"
    web_pkg = "acroform-filler-web"

    workflow = _workflow_ok(args.repo, args.tag)
    worker = _package_has_tag(owner, worker_pkg, args.tag)
    web = _package_has_tag(owner, web_pkg, args.tag)

    report = {"workflow": workflow, "workerImage": worker, "webImage": web}
    report["ok"] = bool(workflow.get("ok")) and bool(worker.get("ok")) and bool(web.get("ok"))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)
