# Repository Guidelines

This repository contains three independent Next.js + TypeScript sample apps demonstrating OpenAI Structured Outputs.

## Project Structure & Module Organization

- Apps: `conversational-assistant/`, `generative-ui/`, `resume-extraction/` (each standalone).
- Inside each app: `app/` (routes, API handlers), `components/` (UI), `lib/` (utils, schemas), `config/` (assistant/tools), `public/` (assets), `stores/` (state; assistant only).
- Use the `@/` path alias for in‑app imports (see each `tsconfig.json`). Avoid deep `../../` chains.
- Place new modules with their feature area; keep files small and focused.

## Build, Test, and Development Commands

Run commands per app directory:

- Install: `cd <app> && npm i`
- Dev: `npm run dev` (serves at `http://localhost:3000`)
- Lint: `npm run lint`
- Build: `npm run build`
- Start (prod): `npm run start`

Set `OPENAI_API_KEY` in `<app>/.env` or your shell. Never commit `.env`.

## Coding Style & Naming Conventions

- Language: TypeScript, React function components, Next.js App Router.
- Formatting (Prettier): 2 spaces, no semicolons, single quotes, `arrowParens: "avoid"`, no trailing commas. Honor configured `importOrder`.
- Linting: ESLint (`next/core-web-vitals`, `next/typescript`). Fix with `npm run lint -- --fix` when reasonable.
- Files: `kebab-case` (e.g., `tool-call.tsx`); exported React components use `PascalCase`.

## Testing Guidelines

- No tests today. If adding:
  - Use Jest + React Testing Library; Playwright for E2E.
  - Co‑locate as `*.test.ts(x)` or `__tests__/` near the source.
  - Add a `test` script to the app’s `package.json` and brief setup notes in the app README.

## Commit & Pull Request Guidelines

- Commits: concise, imperative mood; scope when helpful.
  - Examples: `add carousel for order selection`, `fix tool result rendering`, `update readme with screenshots`.
- PRs: include description, affected app(s), repro/verification steps, screenshots/GIFs for UI, and linked issues.
- Checks: `npm run lint` passes; update app README for UI/API changes; do not commit secrets.

## Security & Configuration Tips

- Configure `OPENAI_API_KEY` per app via `.env`/`.env.local` (git‑ignored).
- Avoid logging secrets. Sanitize and validate inputs sent to models/tools.
- Review external contributions for prompt‑injection and tool invocation safety.

