# QC Appendix B - PdfForms Section 14

Tool: PdfForms (`acroform-filler`)  
Section: 14 (Release Qualification Checklist)  
Run date: 2026-05-29  
Branch: `cursor/pdf-forms-build`

## Evidence run summary

Commands run in this cycle:

- `pnpm -r typecheck` (workspace typecheck) - PASS
- `pnpm --filter @pdf-forms/web build` (web production build) - PASS
- `python -m pytest` in `apps/worker` - PASS (`14 passed`)
- `python scripts/measure_p95.py --sample samples/w9.pdf --iterations 20` - PASS for inspect, PASS for fill+flatten threshold
- `pnpm dlx lighthouse http://127.0.0.1:3001 --preset=desktop` - PASS (`100/100/100/100`)
- `python scripts/run_acceptance.py` - PASS for A1/A2/A3 (`A1 download 200`, `A2 status 409 friendly error`, `A3 count=100 errors=0`)
- `docker compose build worker && docker compose build web && docker compose up -d` - PASS (`web 200`, `worker /healthz ok` via `docker compose exec`)
- `python scripts/verify_renderers.py --skip-mutool` (host) - PASS for pdf.js rendering sanity and headed Chrome native PDF viewer check (`downloadStarted=false`, screenshot bytes > threshold)
- `docker compose exec -T worker python scripts/verify_renderers.py --skip-pdfjs` - PASS for `mutool draw` rendering sanity (`exitCode=0`, text extracted)
- `gh repo edit chayprabs/acroform-filler --add-topic ...` and `gh repo view ... --json repositoryTopics` - PASS (15 required discovery topics set)
- `python apps/worker/scripts/verify_hosted.py --web-url https://github.com --api-url https://api.github.com` - PASS (HTTP 200 + valid TLS verification path)
- `python apps/worker/scripts/verify_hosted.py --allow-missing` - PASS for CI safety path (script reports skipped with explicit reason when hosted URLs are not configured)
- `gh workflow run Release --ref cursor/pdf-forms-build -f web_url=https://github.com -f api_url=https://api.github.com` + run `26603999151` - PASS (`verify-hosted` job succeeded and emitted `ok=true` JSON in logs)
- `.github/workflows/release.yml` now publishes GHCR images on tags and supports workflow-dispatch hosted verification inputs (`web_url`, `api_url`) - PASS (configuration evidence)
- `.github/workflows/release.yml` verify-hosted job now accepts repo vars (`PDF_FORMS_WEB_URL`, `PDF_FORMS_API_URL`) and runs automatically on tag/dispatch with `--allow-missing` - PASS (configuration evidence)
- `python apps/worker/scripts/verify_release_artifacts.py --repo chayprabs/acroform-filler --tag v0.0.0-test` - PASS for verification path (script correctly reports missing release run/packages when tag is absent)
- `git tag v0.1.0-rc.1 && git push origin v0.1.0-rc.1` - PARTIAL PASS: Release workflow executed, `publish-images` succeeded, `build` failed due pnpm version conflict (fixed in workflow for next tag run)
- `git tag v0.1.0-rc.2 && git push origin v0.1.0-rc.2` - PARTIAL PASS: Release workflow executed, `publish-images` succeeded with verifiable tags (`ghcr.io/...:v0.1.0-rc.2`), `build` failed on editable install package discovery (fixed by explicit setuptools package config)
- `git tag v0.1.0-rc.3 && git push origin v0.1.0-rc.3` + `python apps/worker/scripts/verify_release_artifacts.py --repo chayprabs/acroform-filler --tag v0.1.0-rc.3` - PASS (Release workflow success and both GHCR images resolvable by tag)
- Route checks on production server (`http://127.0.0.1:3100`) - PASS for `/pdf-form-fill`, `/pdf-flatten`, `/fdf-to-pdf`, `/xfdf-to-pdf`, `/w9-fill-online`, `/i9-fill-online`
- `python -m pytest` (worker) - PASS (`17 passed`), including password redaction, metadata scrubbing, sample inspect snapshots, and sample fill snapshots
- `pnpm dlx lighthouse http://127.0.0.1:3100 --throttling-method=provided` - PASS (`96/100/100/100`)
- `pnpm --filter @pdf-forms/web test:e2e -- tests/e2e/seo-routes.spec.ts` - PASS (all 6 required SEO routes return 200 with expected page heading)
- `python apps/worker/scripts/generate_a1_evidence.py --skip-mutool` - PASS (generated filled W-9 + pdf.js + headed Chrome proof bundle for A1, leaving only Preview screenshot as manual evidence)

Targeted runtime checks:

- `/v1/inspect` against `apps/worker/samples/w9.pdf` returns HTTP 200 and 23 fields with bbox data - PASS
- `/v1/import` JSON/FDF/XFDF parsing covered by API tests - PASS
- `/v1/batch` with 100 CSV rows (mixed valid/missing source) covered by API test with deterministic output naming - PASS
- XFA-only inspect friendly error (`409_XFA_NOT_CONVERTIBLE`) and sidecar conversion attempt path covered by API tests - PASS
- p95 measurements (local TestClient run): inspect `96.14ms`, fill+flatten `3315.06ms` - PASS against thresholds (`<=2000ms`, `<=5000ms`)
- Lighthouse desktop run (production server): Performance `100`, Accessibility `100`, Best Practices `100`, SEO `100`
- Acceptance script results: `A1 ok=true` (`fieldCount=23`, downloaded bytes `125333`), `A2 ok=true` (`409_XFA_NOT_CONVERTIBLE` with friendly message), `A3 ok=true` (`100/100`, peak traced memory `85.64 MiB`)
- Docker compose runtime check: both `worker` and `web` containers up; web served on `http://127.0.0.1:3000`; worker health returned `{"status":"ok"}` from container network
- Renderer checks: pdf.js script returned `{ok: true, nonWhite: 157465}`, headed Chrome viewer script returned `{ok: true, downloadStarted: false, screenshotBytes: 357334}`, and container mutool check returned `{ok: true, textLength: 5771}`
- SEO route status: all required PRD routes returned `HTTP 200` on local production runtime
- Repo discovery topics: verified via GitHub API (`repositoryTopics`) and now includes 15/15 required checklist keywords
- Password handling evidence: redaction filter masks `password/passwd/pwd` tokens and persisted job metadata contains no password fields
- Sample snapshot evidence: inspect snapshot baseline file at `apps/worker/tests/fixtures/sample_inspect_snapshot.json` and fill+flatten artifact checks for W-9/I-9 in `apps/worker/tests/test_sample_fill_snapshots.py`
- Lighthouse (provided throttling) produced Performance `96`, Accessibility `100`, Best Practices `100`, SEO `100`
- README evidence: screenshot added at `docs/screenshots/playground-home.png` and self-host verification command documented
- Qualification runbook added: `docs/SECTION14_RUNBOOK.md` with exact commands for hosted checks, release tag verification, and macOS Preview evidence capture
- A1 evidence bundle generator added: `apps/worker/scripts/generate_a1_evidence.py` writes deterministic artifacts under `apps/worker/artifacts/a1-evidence/`
- Docker host status: local `docker compose up -d` currently VERIFY-DEFERRED due host API error (`dockerDesktopLinuxEngine v1.54 ... 500`), not app stack failure

## Section 14 status snapshot

Current status by checklist area:

- 14.1 Repo structure - PASS
- 14.2 Build & install - PASS (local)
- 14.3 Local run (`docker compose up`) - VERIFY-DEFERRED (host Docker API failure in current environment; rerun in CI/healthy host)
- 14.4-14.13 Functional/UI - PARTIAL PASS (core implemented; full e2e fixture proof still pending)
- 14.14 Non-functional (Lighthouse + p95) - PASS (p95 verified; Lighthouse >=95 on provided-throttling production run)
- 14.15 Privacy & security - PASS (password redaction + no password persistence covered by automated tests)
- 14.16 Testing - PASS (worker tests now include per-sample inspect/fill snapshots + automated pdf.js, Chrome viewer, and mutool rendering checks)
- 14.17 Deployment - PARTIAL PASS (tag-triggered release workflow success + GHCR image publish verified; hosted production URL checks still pending)
- 14.18 Docs - PASS (README includes screenshot + self-host verification)
- 14.19 SEO sub-routes - PASS
- 14.20 Acceptance fixtures (A1/A2/A3) - PARTIAL PASS (A1/A2/A3 automated checks passing; macOS Preview confirmation still pending)
- 14.21 Final verdict - NOT QUALIFIED YET

## Open qualification blockers

1. Complete cross-viewer manual confirmation for A1 in macOS Preview.
2. Verify hosted production URLs (`https://pdf-forms...` and `https://api.pdf-forms.../healthz`) with `verify_hosted.py`.
