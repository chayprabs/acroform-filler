from __future__ import annotations

import argparse
import json
import os
import ssl
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def _fetch(url: str, timeout: float) -> dict[str, object]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read(256)
            return {
                "ok": 200 <= res.status < 300,
                "status": res.status,
                "url": res.geturl(),
                "bodySample": body.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as err:
        return {"ok": False, "status": err.code, "url": url, "error": str(err)}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "status": None, "url": url, "error": str(err)}


def _tls(hostname: str, port: int, timeout: float) -> dict[str, object]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as secure:
                cert = secure.getpeercert()
        return {
            "ok": True,
            "subject": cert.get("subject"),
            "issuer": cert.get("issuer"),
            "notAfter": cert.get("notAfter"),
        }
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "error": str(err)}


def _default_api_url_from_web(web_url: str) -> str:
    parsed = urlparse(web_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    host = parsed.hostname or ""
    api_host = f"api.{host}"
    return f"{parsed.scheme}://{api_host}/healthz"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", required=False, help="Hosted web URL (e.g. https://pdf-forms.example)")
    parser.add_argument("--api-url", required=False, help="Hosted API health URL (e.g. https://api.pdf-forms.example/healthz)")
    parser.add_argument("--derive-api-from-web", action="store_true")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--output", help="Optional path to write JSON report")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    web_url = args.web_url or os.getenv("PDF_FORMS_WEB_URL", "")
    api_url = args.api_url or os.getenv("PDF_FORMS_API_URL", "")
    if not api_url and args.derive_api_from_web and web_url:
        api_url = _default_api_url_from_web(web_url)

    if not web_url or not api_url:
        report = {
            "ok": False,
            "skipped": args.allow_missing,
            "reason": "Missing web/api URL. Provide args or env vars PDF_FORMS_WEB_URL and PDF_FORMS_API_URL.",
        }
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        sys.exit(0 if args.allow_missing else 2)

    web = _fetch(web_url, args.timeout)
    api = _fetch(api_url, args.timeout)

    web_host = urlparse(web_url).hostname
    api_host = urlparse(api_url).hostname
    tls = {
        "web": _tls(web_host, 443, args.timeout) if web_host else {"ok": False, "error": "invalid web host"},
        "api": _tls(api_host, 443, args.timeout) if api_host else {"ok": False, "error": "invalid api host"},
    }

    report = {"web": web, "api": api, "tls": tls}
    report["ok"] = bool(web.get("ok")) and bool(api.get("ok")) and bool(tls["web"].get("ok")) and bool(tls["api"].get("ok"))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)
