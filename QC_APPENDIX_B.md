# QC Appendix B - PdfForms Section 14

Tool: PdfForms (`acroform-filler`)  
Section: 14 (Release Qualification Checklist)  
Run date: 2026-05-29  
Branch: `cursor/pdf-forms-build`

## Evidence run summary

Commands run in this cycle:

- `pnpm -r typecheck` (workspace typecheck) - PASS
- `pnpm --filter @pdf-forms/web build` (web production build) - PASS
- `python -m pytest` in `apps/worker` - PASS (`11 passed`)
- `python scripts/measure_p95.py --sample samples/w9.pdf --iterations 20` - PASS for inspect, PASS for fill+flatten threshold
- `pnpm dlx lighthouse http://127.0.0.1:3001 --preset=desktop` - PASS (`100/100/100/100`)
- `python scripts/run_acceptance.py` - PASS for A1 and A3 (`A1 download 200`, `A3 count=100 errors=0`)
- `docker compose build worker && docker compose build web && docker compose up -d` - PASS (`web 200`, `worker /healthz ok` via `docker compose exec`)
- `python scripts/verify_renderers.py --skip-mutool` (host) - PASS for pdf.js rendering sanity (`nonWhite` pixels > threshold)
- `docker compose exec -T worker python scripts/verify_renderers.py --skip-pdfjs` - PASS for `mutool draw` rendering sanity (`exitCode=0`, text extracted)

Targeted runtime checks:

- `/v1/inspect` against `apps/worker/samples/w9.pdf` returns HTTP 200 and 23 fields with bbox data - PASS
- `/v1/import` JSON/FDF/XFDF parsing covered by API tests - PASS
- `/v1/batch` with 100 CSV rows (mixed valid/missing source) covered by API test with deterministic output naming - PASS
- XFA-only inspect friendly error (`409_XFA_NOT_CONVERTIBLE`) and sidecar conversion attempt path covered by API tests - PASS
- p95 measurements (local TestClient run): inspect `96.14ms`, fill+flatten `3315.06ms` - PASS against thresholds (`<=2000ms`, `<=5000ms`)
- Lighthouse desktop run (production server): Performance `100`, Accessibility `100`, Best Practices `100`, SEO `100`
- Acceptance script results: `A1 ok=true` (`fieldCount=23`, downloaded bytes `125333`), `A3 ok=true` (`100/100`, peak traced memory `85.47 MiB`)
- Docker compose runtime check: both `worker` and `web` containers up; web served on `http://127.0.0.1:3000`; worker health returned `{"status":"ok"}` from container network
- Renderer checks: pdf.js script returned `{ok: true, nonWhite: 157465}` and container mutool check returned `{ok: true, textLength: 5771}`

## Section 14 status snapshot

Current status by checklist area:

- 14.1 Repo structure - PARTIAL PASS (topics still pending manual repo settings verification)
- 14.2 Build & install - PASS (local)
- 14.3 Local run (`docker compose up`) - PASS
- 14.4-14.13 Functional/UI - PARTIAL PASS (core implemented; full e2e fixture proof still pending)
- 14.14 Non-functional (Lighthouse + p95) - PARTIAL PASS (p95 verified; Lighthouse desktop preset verified, mobile preset still below target)
- 14.15 Privacy & security - PARTIAL PASS (password not persisted path implemented; explicit log audit pending)
- 14.16 Testing - PASS (worker tests + automated pdf.js and mutool rendering checks recorded)
- 14.17 Deployment - PARTIAL PASS (local container images build successfully; hosted URL checks still pending)
- 14.18 Docs - PASS (README/governance/security docs added)
- 14.19 SEO sub-routes - NOT YET VERIFIED
- 14.20 Acceptance fixtures (A1/A2/A3) - PARTIAL PASS (A1+A3 automated checks passing; A2 covered by API tests; cross-viewer manual verification still pending)
- 14.21 Final verdict - NOT QUALIFIED YET

## Open qualification blockers

1. Stabilize Lighthouse mobile preset to >=95 on all four categories.
2. Complete cross-viewer manual confirmation for A1 in macOS Preview and Chrome PDF viewer.
3. Verify hosted URLs and release artifacts (container publish and hosted API/web checks).
