# Build context: repository root (needs the pnpm workspace + packages/shared).
FROM node:22-alpine AS deps
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN pnpm install --frozen-lockfile=false

FROM deps AS build
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ARG NEXT_PUBLIC_DEMO_MODE=true
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE \
    NEXT_TELEMETRY_DISABLED=1
COPY packages/shared packages/shared
COPY apps/web apps/web
RUN pnpm --filter @fogroom/web build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S fogroom && adduser -S fogroom -G fogroom
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /repo/apps/web/public ./apps/web/public
USER fogroom
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
