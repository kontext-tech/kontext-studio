# Kontext Catalog

Catalog connection management, document retrieval, and semantic schema search.

Organised into two cohesive subpackages plus the job definitions:

| Path | Contains |
| --- | --- |
| `indexing/` | Knowledge index (`catalog_index.py`), document extraction/indexing (`document_extractor.py`, `document_index.py`), embeddings (`embedding.py`), LanceDB backend (`lancedb_index.py`), storage paths (`storage_paths.py`) |
| `connections/` | Connection management (`management.py`), provider registry (`providers.py`), internal Iceberg lakehouse (`lakehouse.py`) |
| `jobs/` | Catalog-owned background jobs (external sync, OKF enrichment) |
| `sync_dispatch.py` | Queued dispatch helpers for catalog sync work |

Import concrete symbols from the subpackage that owns them
(`kontext.catalog.indexing...`, `kontext.catalog.connections...`); the package
root re-exports the common ones.
