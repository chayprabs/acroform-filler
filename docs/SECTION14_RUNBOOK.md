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

CI wiring:

- Set repository variables:
  - `PDF_FORMS_WEB_URL`
  - `PDF_FORMS_API_URL`
- `release.yml` runs hosted verification automatically on tags (and workflow_dispatch) using those vars or explicit inputs.
- Release workflow uploads `hosted-verification` artifact containing `verify-hosted.json` for audit retention.

Optional helper to configure hosted URLs in repo variables:

```bash
python apps/worker/scripts/configure_hosted_urls.py \
  --web-url https://pdf-forms.<your-domain> \
  --api-url https://api.pdf-forms.<your-domain>/healthz
```

## 1.1) Local Section 14 audit bundle

Run:

```bash
python apps/worker/scripts/run_section14_local.py --skip-hosted
```

Output:

- `apps/worker/artifacts/section14/local-audit.json`

This audit aggregates pytest, p95, acceptance, renderer checks, and SEO route e2e into one machine-readable report.

For a compact qualification verdict report:

```bash
python apps/worker/scripts/section14_report.py
```

Output:

- `apps/worker/artifacts/section14/section14-report.json`

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

Or run:

```bash
python apps/worker/scripts/verify_release_artifacts.py \
  --repo <owner>/acroform-filler \
  --tag v1.0.0-rc.1
```

Attach workflow URL and package links to `QC_APPENDIX_B.md`.

## 3) A1 macOS Preview evidence (14.20)

On a macOS machine:

1. Generate evidence bundle:

```bash
python apps/worker/scripts/generate_a1_evidence.py
```

This writes:

- `apps/worker/artifacts/a1-evidence/a1-filled-w9.pdf`
- `apps/worker/artifacts/a1-evidence/a1-evidence.json`

2. Confirm `a1-evidence.json` shows `pdfjs.ok = true`, `chromeViewer.ok = true`, and `mutool.ok = true` (or run without mutool skip in CI/container).
3. Open `a1-filled-w9.pdf` in Preview.
4. Confirm text and checkbox values are visible.
5. Capture one screenshot and add it to `docs/screenshots/`.

Attach screenshot path and `a1-evidence.json` summary to `QC_APPENDIX_B.md`.

Only the macOS Preview confirmation remains manual after running the generator.
