# Contributing

## Setup

1. `pnpm install`
2. `cd apps/worker && python -m pip install -e .[dev]`

## Development

- Web: `pnpm --filter @pdf-forms/web dev --port 3000`
- Worker: `cd apps/worker && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

## Tests

- Web type checks: `pnpm -r typecheck`
- Web build: `pnpm --filter @pdf-forms/web build`
- Worker tests: `cd apps/worker && python -m pytest`

## Commit format

Use Conventional Commits, for example:

- `feat(worker): add inspect endpoint`
- `fix(web): handle import parse errors`

## Pull requests

- Include a short summary and verification steps.
- Link requirements/checklist items affected by the change.
