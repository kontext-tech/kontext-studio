# Kontext docs site

Astro Starlight site that publishes the user guide and selected developer
reference pages. The Markdown under `docs/` remains the source of truth; the
generated content collection is gitignored.

## Commands

```bash
pnpm docs:site:sync     # regenerate src/content/docs from docs/
pnpm docs:site:dev      # sync, then start the dev server
pnpm docs:site:build    # sync, then build to docs-site/dist
pnpm docs:site:preview  # serve the built site
```

`dev` and `build` run the sync first, so there is no separate step to remember.

## What is published

- The user guide: every page in `tools/docs-capture/pages.mjs` with
  `status: "published"`.
- The developer reference pages listed in `site-manifest.mjs`.

Plans, decision records, and roadmaps are deliberately excluded, even when they
live under `docs/`. To publish another reference page, add it to
`site-manifest.mjs`; it appears in the sidebar and the developer index.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCS_SITE_URL` | `https://docs.kontext.tech` | Canonical site URL used by Starlight and the sitemap |
| `DOCS_BASE` | `/` | Base path when hosting under a prefix instead of a subdomain |
| `DOCS_REPO_URL` | `https://github.com/kontext-labs/kontext-labs` | Repository used for source links and the GitHub icon |

The sync step rewrites relative source links to site routes, links to source
files to repository URLs, and strips the capture markers that the user-guide
harness writes into the generated blocks.
