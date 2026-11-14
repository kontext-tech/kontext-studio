# Kontext — Copilot Instructions (adapter)

This file is an adapter for GitHub Copilot. The canonical agent guide is
**AGENTS.md** (repo root) — read it first for the full architecture map, build
commands, and conventions. Longer workflows live in `.github/skills/<name>/SKILL.md`.

Inline non-negotiables (because this adapter path is auto-loaded but cannot be
kept in sync):

- Use `pnpm` for Node/TypeScript and `uv` for Python. Never `npm`, `yarn`, or `pip`.
- Verify before finishing: run the affected package's tests, or its
  lint/typecheck/build when it has no tests. State what you ran and did not run.
- Never hand-edit a package version; all packages share one lockstep version
  bumped with `pnpm run version:studio`.
- Follow Conventional Commits (`.github/skills/commit-message`).
- Shared TS packages must not import app-local modules; internal Python DTOs
  belong in `kontext-common` while wire payloads live in the `ts/schema`
  pipeline.
