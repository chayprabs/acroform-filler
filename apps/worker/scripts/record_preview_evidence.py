from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", required=True, help="Path to macOS Preview screenshot file")
    parser.add_argument("--out-image", default="docs/screenshots/a1-preview-macos.png")
    parser.add_argument("--out-manifest", default="apps/worker/artifacts/a1-evidence/preview-evidence.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    src = Path(args.screenshot).resolve()
    if not src.exists():
        print(json.dumps({"ok": False, "reason": f"screenshot not found: {src}"}, indent=2))
        raise SystemExit(2)

    out_image = (repo_root / args.out_image).resolve()
    out_image.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out_image)

    manifest = {
        "ok": True,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "sourcePath": str(src),
        "storedPath": str(out_image),
        "bytes": out_image.stat().st_size,
    }
    out_manifest = (repo_root / args.out_manifest).resolve()
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
