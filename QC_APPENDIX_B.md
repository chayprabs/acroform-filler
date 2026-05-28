# QC Appendix B - PdfForms Section 14

Tool: PdfForms (`acroform-filler`)  
Section: 14 (Release Qualification Checklist)  
Run date: 2026-05-29  
Branch: `cursor/pdf-forms-build`

## Evidence run summary

Commands run in this cycle:

- `pnpm -r typecheck` (workspace typecheck) - PASS
- `pnpm --filter @pdf-forms/web build` (web production build) - PASS
- `python -m pytest` in `apps/worker` - PASS (`10 passed`)

Targeted runtime checks:

- `/v1/inspect` against `apps/worker/samples/w9.pdf` returns HTTP 200 and 23 fields with bbox data - PASS
- `/v1/import` JSON/FDF/XFDF parsing covered by API tests - PASS
- `/v1/batch` with 100 CSV rows (mixed valid/missing source) covered by API test with deterministic output naming - PASS
- XFA-only inspect friendly error (`409_XFA_NOT_CONVERTIBLE`) and sidecar conversion attempt path covered by API tests - PASS

## Section 14 status snapshot

Current status by checklist area:

- 14.1 Repo structure - PARTIAL PASS (topics still pending manual repo settings verification)
- 14.2 Build & install - PASS (local)
- 14.3 Local run (`docker compose up`) - NOT YET VERIFIED
- 14.4-14.13 Functional/UI - PARTIAL PASS (core implemented; full e2e fixture proof still pending)
- 14.14 Non-functional (Lighthouse + p95) - NOT YET VERIFIED
- 14.15 Privacy & security - PARTIAL PASS (password not persisted path implemented; explicit log audit pending)
- 14.16 Testing - PARTIAL PASS (worker tests in place; appearance render checks in pdf.js + mutool pending)
- 14.17 Deployment - NOT YET VERIFIED
- 14.18 Docs - PASS (README/governance/security docs added)
- 14.19 SEO sub-routes - NOT YET VERIFIED
- 14.20 Acceptance fixtures (A1/A2/A3) - PARTIAL PASS (A2 path tested; A1 viewer verification and A3 leak profile pending)
- 14.21 Final verdict - NOT QUALIFIED YET

## Open qualification blockers

1. Run and record Lighthouse >= 95.
2. Measure and record p95 inspect <= 2s and fill+flatten <= 5s.
3. Verify appearance rendering parity in pdf.js and `mutool draw`.
4. Execute acceptance fixture A1 across pdf.js/Preview/Chrome.
5. Execute acceptance fixture A3 (100 PDFs) with leak checks.
6. Validate docker compose runtime and hosted/deployment checks.
