# Section 14 Qualification Runbook

This runbook captures the remaining operator steps required to move `QC_APPENDIX_B.md` from partial pass to full qualification.

## 1) Hosted URL verification (14.17 / 14.15 HTTPS)

Run:

```bash
python apps/worker/scripts/verify_hosted.py \
  --web-url https://pdf-forms.<your-domain> \
  --api-url https://api.pdf-forms.<your-domain>/healthz
```

Expected:

- `web.ok = true`
- `api.ok = true`
- `tls.web.ok = true`
- `tls.api.ok = true`
- process exits `0`

Attach JSON output to `QC_APPENDIX_B.md`.

## 2) Release artifact verification (14.17)

1. Tag the branch:

```bash
git tag v1.0.0-rc.1
git push origin v1.0.0-rc.1
```

2. Verify `release.yml` completed successfully.
3. Confirm GHCR packages exist:
   - `ghcr.io/<owner>/acroform-filler-worker:<tag>`
   - `ghcr.io/<owner>/acroform-filler-web:<tag>`

Attach workflow URL and package links to `QC_APPENDIX_B.md`.

## 3) A1 macOS Preview evidence (14.20)

On a macOS machine:

1. Produce a filled W-9 from the app.
2. Open output in Preview.
3. Confirm text and checkbox values are visible.
4. Capture one screenshot and add it to `docs/screenshots/`.

Attach the screenshot path and result to `QC_APPENDIX_B.md`.
