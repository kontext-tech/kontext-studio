# Kontext Runtime

Runtime composition, bootstrap, and deployment-profile wiring for Kontext.

This is the composition layer: it selects providers/backends and wires them
together. It is the only package that imports both `kontext-engine` (query
compute) and `kontext-kernel` (Python execution topology).

## Naming

- `local` refers to the deployment profile: local auth, SQLite, local filesystem, and local bootstrap defaults.
- `inprocess` refers to the execution topology: services and engines are resolved and executed inside the current Python process.

That means a local profile currently uses an in-process runtime provider, but those are not the same concept.

## Python execution

- Execution topology (childprocess harness, wire protocol, kernel manager) lives
  in `kontext-kernel`.
- Backend **selection** — `create_python_runner_backend` — lives here because it
  needs the managed interpreter (`resolve_managed_python_executable`) and is a
  composition concern.
- The managed virtualenv the kernel runs in lives in
  `kontext.runtime.python_environment`.
