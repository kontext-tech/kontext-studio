kontext-schema
================

Pydantic models for Kontext generated from the shared OpenAPI schemas.

- Source of truth: the Zod models under `ts/schema/src`, exported to
  `ts/schema/src/schemas/kontext.models.openapi.json`
- Generator: `datamodel-code-generator` (Pydantic v2), pinned in the root `uv.lock`
- Install: managed via the repository `uv` workspace

This package uses a src layout and re-exports all generated model classes at
`kontext.schema` for convenient imports. Generated modules live in
`kontext/schema/_generated/`; `base.py`, `policies.py`, and `__init__.py` are
hand-written.

Example:

```python
from kontext.schema import ChatRequest, NotebookDocument
```
