"""Kontext kernel: the separate-process execution topology for Python jobs.

This package owns *execution topology* — how Python code runs in an isolated
child process — separately from deployment composition (``kontext-runtime``):

* :mod:`kontext.kernel.contracts` — dependency-free execution contracts
  (``PythonRunnerRequest`` / ``PythonRunnerResult`` and the backend/bridge
  protocols).
* :mod:`kontext.kernel.protocol` — wire contract (channels, message types,
  connection file).
* :mod:`kontext.kernel.harness` — the stdlib-only child process.
* :mod:`kontext.kernel.manager` — parent-side client and lifecycle.
* :mod:`kontext.kernel.sessions` — the persistent session-kernel pool.
* :mod:`kontext.kernel.runner` / ``session_runner`` — execution entry points
  that return a ``PythonRunnerResult``.

Backend selection (choosing the kernel backend and managed interpreter) lives in
``kontext-runtime`` because it is composition. Import symbols from the submodule
that owns them.
"""
