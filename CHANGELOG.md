## Unreleased

### Feat

- **oss**: commit generated SDK clients and add OSS docs and CI
- **okf**: add open knowledge format support with enrichment job
- **chat**: add per-run chat session token usage tracking
- remove stale session validation logic by month in backend and ui.
- **workflows**: add generic workflow backend infrastructure and remove UI
- **files**: add prefix-based folder support
- **commit-message**: add skill for generating conventional commit messages
- **host-api**: introduce host-api and refactor related components
- **ci**: publish python packages through releases
- **release**: publish labs packages under kontext-labs scope
- **pre-push**: add Commitizen branch check script

### Fix

- **ci**: grant pull-requests read so paths-filter can run on PRs
- **catalog**: avoid network INSTALL on every Excel read
- release workflow lockfile drift after SDK artifact install (#2)
- **resolver**: update headers and base_url retrieval in resolve_model_selection
- **ci**: clean stale python release assets
- **ci**: patch sdk artifact install and llm package resources
- **ci**: publish python release assets without pages
- **ci**: enable pages for python package index
- **ci**: resolve python dist output path
- **release**: use package token for npm publish
- **release**: remove unsupported changesets flag

### Refactor

- **query**: name subpath barrels after their public import paths
- **naming**: drop I-prefix from service interfaces and enforce symbol naming
- **ts**: enforce filename convention at src root and align barrels
- **naming**: align script names with repo conventions and current product
- **chat**: remove workflow and plan modes from chat interface
- **auth**: split labs local setup from hosted auth
- **boundaries**: narrow package ownership
- **host**: extract local services and normalize cultures
- **skill**: rename recipe contracts end to end
