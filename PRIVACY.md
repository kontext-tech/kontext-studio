# Kontext Studio Privacy Notice

Kontext Studio is local-first. The application, its API, job worker, and Python
kernels run on your machine, and workspace data is stored in the local workspace
directory you choose (by default `.kontext/`).

## What stays local

- Projects, files, notebooks, chats, query results, and profiles.
- Model-provider credentials, stored in the local workspace.
- Application logs and job history.

## When data leaves your machine

Kontext Studio contacts an external service only when you configure or use one:

- **Model providers** receive the prompts, context, and tool results needed to
  answer your request. Their handling is governed by their own terms and privacy
  policies.
- **Package and model catalogs** are shipped with the application; no catalog
  telemetry is collected.
- **Update and installation** traffic goes to PyPI or GitHub only when you run
  an install or upgrade command.

Kontext Studio does not include analytics or telemetry by default.

## Your choices

- Disconnect or remove a model provider at any time in **Model providers**.
- Delete a project or workspace using the application or your file manager.
- Configure only local providers (for example Ollama or LM Studio) to keep
  prompts on your machine.

## Contact

Privacy questions: [hello@kontext.tech](mailto:hello@kontext.tech).
