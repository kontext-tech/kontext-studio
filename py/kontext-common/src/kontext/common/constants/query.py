"""
Query execution constants.
"""


class QueryConstants:
    """Constants related to query execution and results."""

    # DuckDB resource guards applied when opening a session connection.
    # These prevent a single runaway query from exhausting host memory / disk.
    DUCKDB_MEMORY_LIMIT = "1GB"
    DUCKDB_MAX_THREADS = 4

    # Plan operators that mutate session or external state. DuckDB ``EXPLAIN``
    # binds and plans a statement without executing it, so validation rejects
    # any statement whose physical plan contains one of these operators.
    DUCKDB_WRITE_PLAN_OPERATORS = frozenset(
        {
            "INSERT",
            "DELETE",
            "UPDATE",
            "CREATE_TABLE",
            "CREATE_VIEW",
            "CREATE_INDEX",
            "CREATE_MACRO",
            "CREATE_SECRET",
            "CREATE_TYPE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "COPY_TO_FILE",
            "BATCH_COPY_TO_FILE",
            "COPY_FROM_FILE",
            "EXPORT",
            "IMPORT",
            "ATTACH",
            "DETACH",
            "SET",
            "RESET",
            "CALL",
            "PRAGMA",
            "LOAD",
            "INSTALL",
            "TRANSACTION",
            "COMMIT",
            "ROLLBACK",
        }
    )

    # Number of rows to include in the result preview (for UI/Agent context)
    PREVIEW_ROW_LIMIT = 3

    # Fallback per-query wall-clock bound for in-process session execution.
    # The in-process service holds the process-wide session lock while a query
    # runs, so an unbounded query would silently block every later query on
    # that session (agent tool calls queue behind it). Callers may pass an
    # explicit larger value; None means "use this default", not "infinite".
    DEFAULT_QUERY_TIMEOUT_SECONDS = 120

    # Default internal fetch limit (failsafe)
    # This limits memory usage while allowing for reasonably large result sets.
    MAX_FETCH_ROWS = 100_000

    # Default threshold for storing results as file (if not specified)
    # 500 rows is a reasonable balance:
    # - Small enough to fit in LLM context windows (approx 5-15k tokens)
    #   when embedded in notebooks
    # - Large enough to handle common aggregations without creating small
    #   file clutter in Data Lake
    EXECUTION_PERSIST_THRESHOLD = 500

    # Threshold for embedding data directly into document content
    # (Notebooks/Charts) vs referencing a persistent file.
    # - If rows <= threshold: Embed data in document JSON.
    # - If rows > threshold: Ensure data is persisted to file and use
    #   dataId reference.
    DOCUMENT_EMBEDDING_THRESHOLD = 50
