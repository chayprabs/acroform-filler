from __future__ import annotations

import httpx

from .config import settings


def convert_xfa_to_acroform(data: bytes, password: str | None = None) -> bytes | None:
    url = f"{settings.node_sidecar_url.rstrip('/')}/v1/xfa/convert"
    form_data = {"password": password} if password else None
    try:
        response = httpx.post(
            url,
            files={"file": ("input.pdf", data, "application/pdf")},
            data=form_data,
            timeout=20.0,
        )
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None
    return response.content or None
