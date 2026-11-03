---
name: commit-message
description: Generate conventional commit messages and create the commit automatically - use when creating commits, writing commit messages, or asking for git commit help
---

# Commit Message Skill

Create commits following the Conventional Commits specification.

When this skill is used for a real commit request, do not stop at proposing a message. Inspect the current git state, choose an appropriate Conventional Commit message, and run a non-interactive `git commit` automatically.

## Workflow

1. Inspect `git status --short` and the relevant diff to understand the change set.
2. Choose the most accurate Conventional Commit type and scope from the actual changes.
3. If the user did not explicitly prepare a partial commit, stage only the files relevant to the task and avoid unrelated changes.
4. Create the commit with a non-interactive git command such as `git commit -m "<subject>"` and add extra `-m` flags for body/footer when needed.
5. Report the final commit message and commit hash back to the user.

## Guardrails

- Prefer committing only staged changes when the user has already prepared the index.
- If unstaged changes clearly belong to the same task, stage them before committing.
- Do not include unrelated user changes in the commit.
- Do not amend existing commits unless the user explicitly asks.
- Use non-interactive git commands only.

## Format

```text
<type>(<scope>): <description>

[optional body]

[optional footer]
```

## Types

| Type | When to Use |
| ---- | ----------- |
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting (no code change) |
| `refactor` | Code change that neither fixes nor adds |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |

## Rules

1. Subject line maximum 72 characters
2. Use imperative mood ("add" not "added" or "adds")
3. No period at the end of subject line
4. Separate subject from body with blank line
5. Body explains **what** and **why**, not how

## Examples

Simple:

```text
fix(auth): prevent redirect loop on expired sessions
```

With body:

```text
feat(api): add rate limiting to public endpoints

- Limits requests to 100/minute per IP
- Returns 429 status with retry-after header
- Configurable via RATE_LIMIT_MAX env variable

Closes #234
```
