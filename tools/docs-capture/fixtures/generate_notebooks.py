"""Generate the notebook fixtures from the vendored Chinook database.

Run once after changing the Chinook SQL or the notebook structure:

    .venv/bin/python tools/docs-capture/fixtures/generate_notebooks.py

The output is committed. Aggregates are deterministic because Chinook 1.4.5 is
vendored under fixtures/chinook/.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_FILE = ROOT / "tools/docs-capture/fixtures/chinook/Chinook_Sqlite.sql"
OUT_FILE = ROOT / "tools/docs-capture/fixtures/notebooks.mjs"
EPOCH = int(datetime(2026, 2, 16, 9, 0, tzinfo=UTC).timestamp() * 1000)


def build_db() -> sqlite3.Connection:
    _handle, path = tempfile.mkstemp(suffix=".db")
    Path(path).unlink()
    connection = sqlite3.connect(path)
    connection.executescript(SQL_FILE.read_text())
    connection.commit()
    return connection


def table(columns: list[tuple[str, str]], rows: list[list[object]]) -> dict:
    return {
        "columns": [{"name": name, "type": kind} for name, kind in columns],
        "rows": rows,
        "rowCount": len(rows),
    }


def inline(title: str, columns, rows) -> dict:
    return {"title": title, "table": table(columns, rows)}


def code(block_id: str, text: str, language: str = "python", outputs=None) -> dict:
    return {
        "id": block_id,
        "type": "code",
        "data": {
            "code": text,
            "language": language,
            "runtimePreference": "server",
            "showCode": True,
            "outputs": outputs or [],
        },
    }


def chart(block_id: str, config: dict, data: dict) -> dict:
    inline = data if "table" in data else {"title": config["title"], "table": data}
    return {
        "id": block_id,
        "type": "chart",
        "data": {"config": config, "inlineData": inline},
    }


def uid(n: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kontext-docs-block-{n}"))


def main() -> None:
    db = build_db()
    cur = db.cursor()

    monthly = cur.execute(
        """
        select strftime('%Y-%m', InvoiceDate) as month,
               round(sum(Total), 2) as revenue,
               count(*) as invoices
        from Invoice
        where InvoiceDate >= '2025-01-01'
        group by 1 order by 1
        """
    ).fetchall()

    cumulative = []
    running = 0.0
    for month, revenue, _ in monthly:
        running = round(running + revenue, 2)
        cumulative.append([month, running])

    by_country = cur.execute(
        """
        select BillingCountry as country, round(sum(Total), 2) as revenue
        from Invoice group by 1 order by 2 desc limit 6
        """
    ).fetchall()

    by_genre = cur.execute(
        """
        select g.Name as genre,
               round(sum(il.UnitPrice * il.Quantity), 2) as revenue,
               sum(il.Quantity) as tracks
        from InvoiceLine il
        join Track t on t.TrackId = il.TrackId
        join Genre g on g.GenreId = t.GenreId
        group by 1 order by 3 desc limit 6
        """
    ).fetchall()

    genre_country = cur.execute(
        """
        select g.Name as genre, c.Country as country,
               round(sum(il.UnitPrice * il.Quantity), 2) as revenue
        from InvoiceLine il
        join Invoice i on i.InvoiceId = il.InvoiceId
        join Customer c on c.CustomerId = i.CustomerId
        join Track t on t.TrackId = il.TrackId
        join Genre g on g.GenreId = t.GenreId
        where c.Country in ('USA','Canada','France','Brazil','Germany')
          and g.Name in ('Rock','Latin','Metal','Alternative & Punk','Jazz')
        group by 1, 2 order by 1, 2
        """
    ).fetchall()

    scatter = cur.execute(
        """
        select count(*) as lines, round(sum(Total), 2) as total
        from Invoice group by InvoiceId order by InvoiceId limit 40
        """
    ).fetchall()

    totals = [
        row[0] for row in cur.execute("select round(Total, 2) from Invoice order by InvoiceId")
    ]

    stock = []
    previous = cumulative[-7][1]
    for month, close in cumulative[-6:]:
        low = round(min(previous, close) * 0.98, 2)
        high = round(max(previous, close) * 1.02, 2)
        stock.append([month, previous, close, low, high])
        previous = close

    # ---------------------------------------------------------------- gallery
    monthly_data = table(
        [("month", "varchar"), ("revenue", "decimal"), ("invoices", "int")],
        [list(row) for row in monthly],
    )
    cumulative_data = table([("month", "varchar"), ("cumulative", "decimal")], cumulative)
    country_data = table(
        [("country", "varchar"), ("revenue", "decimal")],
        [list(row) for row in by_country],
    )
    genre_data = table(
        [("genre", "varchar"), ("revenue", "decimal"), ("tracks", "int")],
        [list(row) for row in by_genre],
    )
    genre_country_data = table(
        [("genre", "varchar"), ("country", "varchar"), ("revenue", "decimal")],
        [list(row) for row in genre_country],
    )
    scatter_data = table([("lines", "int"), ("total", "decimal")], [list(row) for row in scatter])
    totals_data = table([("total", "decimal")], [[value] for value in totals])
    stock_data = table(
        [
            ("month", "varchar"),
            ("open", "decimal"),
            ("close", "decimal"),
            ("low", "decimal"),
            ("high", "decimal"),
        ],
        stock,
    )

    gallery_charts = [
        (
            "line",
            {
                "chartType": "line",
                "title": "Monthly revenue",
                "height": 320,
                "xField": "month",
                "yField": "revenue",
                "colorPalette": "kontext",
            },
            monthly_data,
        ),
        (
            "bar",
            {
                "chartType": "bar",
                "title": "Revenue by country",
                "height": 320,
                "xField": "country",
                "yField": "revenue",
                "colorPalette": "kontext",
            },
            country_data,
        ),
        (
            "column",
            {
                "chartType": "column",
                "title": "Tracks sold by genre",
                "height": 320,
                "xField": "genre",
                "yField": "tracks",
                "colorPalette": "kontext",
            },
            genre_data,
        ),
        (
            "area",
            {
                "chartType": "area",
                "title": "Cumulative revenue",
                "height": 320,
                "xField": "month",
                "yField": "cumulative",
                "colorPalette": "kontext",
            },
            cumulative_data,
        ),
        (
            "pie",
            {
                "chartType": "pie",
                "title": "Genre share of revenue",
                "height": 320,
                "angleField": "revenue",
                "colorField": "genre",
                "colorPalette": "kontext",
            },
            genre_data,
        ),
        (
            "scatter",
            {
                "chartType": "scatter",
                "title": "Invoice size and line count",
                "height": 320,
                "xField": "lines",
                "yField": "total",
                "colorPalette": "kontext",
            },
            scatter_data,
        ),
        (
            "dualAxes",
            {
                "chartType": "dualAxes",
                "title": "Revenue and invoice count",
                "height": 320,
                "xField": "month",
                "leftYField": "revenue",
                "leftChartType": "interval",
                "rightYField": "invoices",
                "rightChartType": "line",
                "colorPalette": "kontext",
            },
            monthly_data,
        ),
        (
            "funnel",
            {
                "chartType": "funnel",
                "title": "Revenue funnel by country",
                "height": 320,
                "xField": "country",
                "yField": "revenue",
                "colorPalette": "kontext",
            },
            country_data,
        ),
        (
            "heatmap",
            {
                "chartType": "heatmap",
                "title": "Genre revenue by country",
                "height": 320,
                "xField": "genre",
                "yField": "country",
                "colorField": "revenue",
                "mark": "cell",
                "colorPalette": "blues",
            },
            genre_country_data,
        ),
        (
            "histogram",
            {
                "chartType": "histogram",
                "title": "Distribution of invoice totals",
                "height": 320,
                "binField": "total",
                "colorPalette": "kontext",
            },
            totals_data,
        ),
        (
            "radar",
            {
                "chartType": "radar",
                "title": "Genre strength by country",
                "height": 320,
                "xField": "genre",
                "yField": "revenue",
                "colorField": "country",
                "colorPalette": "kontext",
            },
            genre_country_data,
        ),
        (
            "stock",
            {
                "chartType": "stock",
                "title": "Monthly revenue range",
                "height": 320,
                "xField": "month",
                "yField": ["open", "close", "low", "high"],
                "colorPalette": "kontext",
            },
            stock_data,
        ),
    ]

    gallery_blocks = [
        {
            "id": uid(1),
            "type": "header",
            "data": {"text": "Chart gallery", "level": 2},
        },
        {
            "id": uid(2),
            "type": "paragraph",
            "data": {
                "text": "Every chart type is a notebook block. Each block keeps its "
                "configuration and data together, so the chart reopens exactly as it was saved."
            },
        },
    ]
    for index, (_, config, data) in enumerate(gallery_charts, start=10):
        gallery_blocks.append(chart(uid(index), config, data))

    # ------------------------------------------------------------ feature tour
    revenue_alias_data = inline(
        "Revenue by country",
        [("country", "varchar"), ("revenue", "decimal")],
        [list(row) for row in by_country],
    )

    feature_blocks = [
        {
            "id": uid(100),
            "type": "header",
            "data": {"text": "Block types", "level": 2},
        },
        {
            "id": uid(101),
            "type": "paragraph",
            "data": {
                "text": "A notebook is an ordered list of typed blocks. Every block "
                "below is rendered by the same editor, and the document is saved as JSON."
            },
        },
        {
            "id": uid(102),
            "type": "list",
            "data": {
                "style": "unordered",
                "meta": {},
                "items": [
                    {
                        "content": "Text blocks for prose, lists, and quotes",
                        "meta": {},
                        "items": [],
                    },
                    {"content": "Data blocks for SQL, tables, and charts", "meta": {}, "items": []},
                    {"content": "Code blocks for Python", "meta": {}, "items": []},
                ],
            },
        },
        {"id": uid(104), "type": "delimiter", "data": {}},
        {
            "id": uid(105),
            "type": "table",
            "data": {
                "withHeadings": True,
                "content": [
                    ["Block", "Use it for"],
                    ["SQL", "Query a data source and keep the result"],
                    ["Chart", "Visualise a result table"],
                    ["Python", "Transform or inspect data"],
                ],
            },
        },
        {
            "id": uid(106),
            "type": "sql",
            "data": {
                "title": "Revenue by country",
                "alias": "revenue_by_country",
                "code": "select BillingCountry as country,\n       round(sum(Total), 2) as revenue\nfrom Invoice\ngroup by 1\norder by 2 desc\nlimit 6;",
                "showResults": True,
                "lastExecuted": EPOCH,
                "inlineData": revenue_alias_data,
            },
        },
        {
            "id": uid(1065),
            "type": "paragraph",
            "data": {
                "text": "The result keeps the alias <code>revenue_by_country</code>, so a "
                "Python block can load it without running the query again."
            },
        },
        code(
            uid(107),
            'revenue = await kontext.load_data("revenue_by_country")\n'
            "print(revenue.head(3).to_string(index=False))",
            outputs=[
                {
                    "type": "text",
                    "mimeType": "text/plain",
                    "content": "  country  revenue\n      USA   523.06\n   Canada   303.96\n   France   195.10",
                }
            ],
        ),
        chart(
            uid(108),
            {
                "chartType": "column",
                "title": "Revenue by country",
                "height": 320,
                "xField": "country",
                "yField": "revenue",
                "colorPalette": "kontext",
            },
            revenue_alias_data,
        ),
        {
            "id": uid(109),
            "type": "mermaid",
            "data": {
                "title": "How a notebook flows",
                "code": "flowchart LR\n  Q[SQL block] --> R[Result table]\n  R --> P[Python block]\n  R --> C[Chart block]",
            },
        },
        {
            "id": uid(110),
            "type": "image",
            "data": {
                "file": {"url": "/icons/favicon.svg", "name": "kontext.svg"},
                "caption": "Image blocks embed a file and an optional caption.",
                "withBorder": True,
                "withBackground": False,
                "stretched": False,
            },
        },
        {
            "id": uid(111),
            "type": "list",
            "data": {
                "style": "checklist",
                "meta": {},
                "items": [
                    {"content": "Query the data", "meta": {"checked": True}, "items": []},
                    {"content": "Chart the result", "meta": {"checked": True}, "items": []},
                    {"content": "Explain the finding", "meta": {"checked": False}, "items": []},
                ],
            },
        },
    ]

    # ---------------------------------------------------------- python workflow
    python_rows = [
        [
            row[0],
            row[1],
            round(row[1] / sum(r[1] for r in by_country) * 100, 1),
        ]
        for row in by_country
    ]
    lines_out = ["  country  revenue  share_pct"]
    for country, revenue, share in python_rows:
        lines_out.append(f"{country:>9}  {revenue:>7.2f}  {share:>9.1f}")
    python_text = "\n".join(lines_out)

    python_blocks = [
        {
            "id": uid(200),
            "type": "header",
            "data": {"text": "SQL and Python share data", "level": 2},
        },
        {
            "id": uid(201),
            "type": "paragraph",
            "data": {
                "text": "Give a SQL block an alias, then load its saved result from a Python "
                'block with <code>await kontext.load_data("revenue_by_country")</code>. '
                "No re-query and no export step."
            },
        },
        {
            "id": uid(202),
            "type": "sql",
            "data": {
                "title": "Revenue by country",
                "alias": "revenue_by_country",
                "code": "select BillingCountry as country,\n       round(sum(Total), 2) as revenue\nfrom Invoice\ngroup by 1\norder by 2 desc\nlimit 6;",
                "showResults": True,
                "lastExecuted": EPOCH,
                "inlineData": revenue_alias_data,
            },
        },
        code(
            uid(203),
            'revenue = await kontext.load_data("revenue_by_country")\n'
            'revenue["share_pct"] = (revenue["revenue"] / revenue["revenue"].sum() * 100).round(1)\n'
            "revenue",
            outputs=[
                {
                    "type": "text",
                    "mimeType": "text/plain",
                    "content": python_text,
                }
            ],
        ),
        {
            "id": uid(204),
            "type": "paragraph",
            "data": {
                "text": "The Python block receives a dataframe, and its output is saved with the "
                "notebook. Python runs in the project runtime, so the same code works after a restart."
            },
        },
    ]

    execution_rows = [
        ("USA", 523.06),
        ("Canada", 303.96),
        ("France", 195.10),
        ("Brazil", 190.10),
    ]
    execution_total = sum(revenue for _, revenue in execution_rows)
    execution_text = "  country  revenue  share_pct"
    for country, revenue in execution_rows:
        execution_text += (
            f"\n{country:>9}  {revenue:>7.2f}  {revenue / execution_total * 100:>9.1f}"
        )

    python_execution_blocks = [
        {
            "id": uid(300),
            "type": "header",
            "data": {"text": "Python execution", "level": 2},
        },
        {
            "id": uid(301),
            "type": "paragraph",
            "data": {
                "text": "A Python block runs server-side and keeps its output with the "
                "notebook. Select Run to execute it again."
            },
        },
        code(
            uid(302),
            "# Revenue share by country\n"
            'rows = [("USA", 523.06), ("Canada", 303.96), ("France", 195.10), ("Brazil", 190.10)]\n'
            "total = sum(revenue for _, revenue in rows)\n"
            "print(f\"{'country':>9}  {'revenue':>7}  {'share_pct':>9}\")\n"
            "for country, revenue in rows:\n"
            '    print(f"{country:>9}  {revenue:>7.2f}  {revenue / total * 100:>9.1f}")\n',
            outputs=[
                {
                    "type": "text",
                    "mimeType": "text/plain",
                    "content": execution_text,
                }
            ],
        ),
    ]

    sql_execution_blocks = [
        {
            "id": uid(400),
            "type": "header",
            "data": {"text": "SQL execution", "level": 2},
        },
        {
            "id": uid(401),
            "type": "paragraph",
            "data": {
                "text": "Select Run on a SQL block to execute it against the notebook's "
                "query session. The block keeps the result and links to the managed run."
            },
        },
        {
            "id": uid(402),
            "type": "sql",
            "data": {
                "title": "Query check",
                "code": "select 1 as check_value;",
                "showResults": True,
            },
        },
    ]

    data_table = {
        "title": "Monthly revenue",
        "table": table(
            [("month", "varchar"), ("revenue", "decimal"), ("invoices", "int")],
            [list(row) for row in monthly],
        ),
    }

    iso_stamp = datetime.fromtimestamp(EPOCH / 1000, UTC).isoformat()
    chart_document = {
        "name": "Revenue by country",
        "metadata": {
            "description": "Revenue by billing country in the Chinook store.",
            "createdAt": iso_stamp,
            "modifiedAt": iso_stamp,
        },
        "config": {
            "chartType": "bar",
            "title": "Revenue by country",
            "height": 420,
            "xField": "country",
            "yField": "revenue",
            "colorPalette": "kontext",
        },
        "inlineData": {
            "title": "Revenue by country",
            "table": {
                "columns": [
                    {"name": "country", "type": "varchar"},
                    {"name": "revenue", "type": "decimal"},
                ],
                "rows": [list(row) for row in by_country],
                "rowCount": len(by_country),
            },
        },
    }

    documents = {
        "chartDocument": chart_document,
        "featureTourNotebook": {
            "title": "Notebook block types",
            "created": EPOCH,
            "modified": EPOCH,
            "blocks": feature_blocks,
        },
        "chartsGalleryNotebook": {
            "title": "Chart gallery",
            "created": EPOCH,
            "modified": EPOCH,
            "blocks": gallery_blocks,
        },
        "pythonWorkflowNotebook": {
            "title": "SQL and Python",
            "created": EPOCH,
            "modified": EPOCH,
            "blocks": python_blocks,
        },
        "pythonExecutionNotebook": {
            "title": "Python execution",
            "created": EPOCH,
            "modified": EPOCH,
            "blocks": python_execution_blocks,
        },
        "sqlExecutionNotebook": {
            "title": "SQL execution",
            "created": EPOCH,
            "modified": EPOCH,
            "blocks": sql_execution_blocks,
        },
        "dataTableDocument": data_table,
    }

    gallery_ids = {kind: uid(10 + index) for index, (kind, _, _) in enumerate(gallery_charts)}

    lines = [
        "// Generated by fixtures/generate_notebooks.py from Chinook 1.4.5.",
        "// Do not edit by hand; re-run the generator instead.",
        "",
        f"export const FIXTURE_EPOCH = {EPOCH};",
        "",
        "export const blockIds = {",
        "   featureTour: {",
        f'      header: "{uid(100)}",',
        f'      table: "{uid(105)}",',
        f'      sql: "{uid(106)}",',
        f'      aliasNote: "{uid(1065)}",',
        f'      code: "{uid(107)}",',
        f'      chart: "{uid(108)}",',
        f'      mermaid: "{uid(109)}",',
        f'      image: "{uid(110)}",',
        "   },",
        "   gallery: {",
        *[f'      {kind}: "{gallery_ids[kind]}",' for kind in gallery_ids],
        "   },",
        "   python: {",
        f'      header: "{uid(200)}",',
        f'      sql: "{uid(202)}",',
        f'      code: "{uid(203)}",',
        "   },",
        "   pythonExecution: {",
        f'      code: "{uid(302)}",',
        "   },",
        "   sqlExecution: {",
        f'      sql: "{uid(402)}",',
        "   },",
        "};",
        "",
    ]
    for name, document in documents.items():
        lines.append(f"export const {name} = {json.dumps(document, indent=3)};")
        lines.append("")

    OUT_FILE.write_text("\n".join(lines))
    print(f"wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
