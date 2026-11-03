# Kontext Kernel

The separate-process execution topology for Kontext Python jobs.

## What This Package Owns

- The dependency-free Python execution contracts (`kontext.kernel.contracts`)
- The child-process harness and wire protocol
- The parent-side kernel manager, session kernel pool, and runner backends

The child harness is deliberately stdlib-only and must not import `kontext`
(see `harness.py`), so the kernel stays isolated from the parent package graph.

## What It Does Not Own

- deployment composition or backend/provider *selection* (see `kontext-runtime`)
- durable run lifecycle (see `kontext-execution`)
- the managed virtualenv that a kernel runs in (see `kontext-runtime`)

Backend selection — choosing the kernel backend and resolving the managed
interpreter — is composition and lives in `kontext-runtime`
(`create_python_runner_backend`, `resolve_managed_python_executable`). This
package has **no dependency on any other Kontext package** so it can be reused
by any deployment profile.

See [Python Package Boundaries](../../docs/development/python-package-boundaries.md).
