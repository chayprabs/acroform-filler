FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json
COPY packages/shared-ui/package.json packages/shared-ui/package.json
RUN corepack enable && pnpm install --frozen-lockfile

FROM deps AS builder
WORKDIR /app
COPY . .
RUN corepack enable && CI=true pnpm install --frozen-lockfile && pnpm --filter @pdf-forms/web build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app /app
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "apps/web", "-p", "3000"]
