# Kontext Studio user guide

Kontext Studio is a local-first, open-source conversational analytics workspace.
Connect your files and databases, bring your own model, and chat with your
data — every answer comes with the SQL, charts, Python code, or notebooks
behind it, ready to inspect and re-run on your machine.

This guide is task-oriented: each page covers one workflow, with the
screens and controls you need. Start with installation if you are new, or
jump to the page for the task you are doing.

## Get started

- [Install and start Kontext Studio](01-install-and-start.md) — Install the released wheel, start the local server, and replace the placeholder profile.
- [Use the macOS desktop app](16-desktop-app.md) — Download the app with its bundled runtime, install it, and keep it updated.
- [Open or create a project](02-create-a-project.md) — Projects hold data sources, files, chats, and settings.

## Data

- [Connect a data source](03-connect-a-data-source.md) — Connect an external database or inspect the default lakehouse.
- [Browse and manage files](04-browse-and-open-files.md) — Upload, organize, search, and open project files.

## Notebooks

- [Work with notebooks](05-work-with-notebooks.md) — Use text, table, SQL, code, chart, diagram, and image blocks in one document.
- [Chart query results](06-chart-results.md) — Every chart type, with the data and configuration saved in the document.
- [Python and data frames](07-python-and-data-frames.md) — Run Python blocks and load SQL results with kontext.load_data, without re-querying.

## Agents and models

- [Chat with an agent](08-chat-with-an-agent.md) — Start a conversation and revisit previous sessions.
- [Ground an agent in knowledge](09-ground-an-agent-in-knowledge.md) — Curate the business concepts agents cite, and review their proposals.
- [Connect a model provider](10-connect-a-model-provider.md) — Add a local or cloud model and choose the default.

## Workspace settings

- [Account](11-account.md) — Review and edit the local profile that owns this workspace.
- [Python environment](12-python-environment.md) — Inspect the runtime that executes notebook and chat Python blocks, and prepare it.
- [Project settings](13-project-settings.md) — Edit the project name and description, and understand local access.
- [Jobs and run details](14-jobs.md) — Monitor background runs and inspect their parameters, logs, and timing.
- [Project overview and usage](15-project-overview.md) — Inspect project details, token and storage usage, and the monthly token history.
