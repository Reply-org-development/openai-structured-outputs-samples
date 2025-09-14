# Multi-stage build for Next.js (Conversational Assistant)
# Node 20 (alpine) for small image size; Next.js 14 supports linux-musl.

FROM node:20-alpine AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Provide a dummy API key at build time to avoid import-time validation in API routes
ENV OPENAI_API_KEY=dummy
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build Next.js (generates .next/standalone for minimal runtime deps)
# Skip lint during Docker build to avoid ESLint CLI option mismatch across environments
RUN npm run build -- --no-lint

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Unset any dummy keys potentially set in prior stages
ENV OPENAI_API_KEY=

# Copy standalone server and static assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
