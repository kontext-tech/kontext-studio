# Kontext OKF

Open Knowledge Format (OKF v0.2) canonical concept model and bundle I/O for Kontext.

This package makes OKF the **source-of-truth model** for curated knowledge
(the `knowledge` scope of the unified knowledge index). OKF concepts are stored
as markdown files with YAML frontmatter (the portable, vendor-neutral OKF
interchange format) and **projected** into the existing LanceDB-backed
`KnowledgeDocument` rows for retrieval — so the index becomes a *derived,
disposable* layer rather than the system of record.

See `docs/` and the OKF v0.2 spec for the frontmatter field semantics.
