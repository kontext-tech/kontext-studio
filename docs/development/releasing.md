# Releasing

A release is cut by one maintainer-dispatched workflow, `release.yml`. It never
runs on a push or a merged pull request, so merging cannot publish an artifact
by itself. The three release artifacts keep separate tag namespaces so they
never contend for the same GitHub Release; the docs site piggybacks on the
`v<version>` release and has no tag of its own.

| Artifact | Workflow | Trigger | Release tag |
| -------- | -------- | ------- | ----------- |
| Unified Python wheel (`kontext_studio-<version>-py3-none-any.whl`) | `publish-pypi.yml` | dispatched by `release.yml`, or `workflow_dispatch` | `v<version>` (GitHub Release + PyPI) |
| `@kontext-tech/*` TypeScript packages (GitHub Packages) | `publish-ts-packages.yml` | `push: tags: ["ts-packages-v*"]` | `ts-packages-v<version>` |
| Docs site (`docs.kontext.tech`) | `publish-docs.yml` | `workflow_call` from `release.yml`, or `workflow_dispatch` | none |

## Cut a release

Dispatch `release.yml` from `main` with:

| Input | Meaning |
| ----- | ------- |
| `bump` | `auto` (Commitizen reads the Conventional Commits), or force `patch`/`minor`/`major`. Ignored when `version` is set. |
| `version` | Release an already-tagged version without bumping. Used to resume. |
| `publish_pypi` | Dispatch `publish-pypi.yml` once the Release exists (default `true`). |
| `publish_docs` | Publish the docs site (default `true`). |
| `prerelease` | Mark the GitHub Release as a prerelease. |

The workflow:

1. Checks out `origin/main`, requires `secrets.PAT_FOR_TAG_PUSH` (see below),
   and runs `validate:workspace-versions`.
2. Runs `cz bump`. It rewrites every `version_files` entry, prepends
   `CHANGELOG.md`, creates the `chore(release): version <old> -> <new>` commit,
   pushes it to `main`, and pushes `ts-packages-v<new>`, which publishes the
   `@kontext-tech/*` packages.
3. Creates or promotes the `v<version>` GitHub Release at the bump commit,
   using the generated changelog section as the release notes.
4. Publishes the docs site (unless `publish_docs` is false).
5. Dispatches `publish-pypi.yml` with `target=pypi`, `version`, and `confirm`
   (unless `publish_pypi` is false). It stays a top-level workflow because PyPI
   trusted publishing does not support reusable workflows.

`publish-pypi.yml` refuses a production publish when `version` differs from the
workspace version or `confirm` differs from `version`, so a typo fails the run
instead of publishing the wrong artifact.

`PAT_FOR_TAG_PUSH` must carry `contents:write` (to push the bump commit to a
protected `main` and to push tags) and `actions:write` (to dispatch
`publish-pypi.yml`). The workflow `GITHUB_TOKEN` cannot push to `main`, and
pushes it makes do not start other workflows.

### Resume a partial release

Publishing is the only stage that can fail after the version is immutable.
Re-dispatch the failed workflow directly:

- **PyPI failed** — dispatch `publish-pypi.yml` with `target=pypi`, `version`,
  and `confirm`.
- **Docs failed** — dispatch `publish-docs.yml`.
- **Tag pushed but the GitHub Release was never created** — re-dispatch
  `release.yml` with `version=<version>`; it skips the bump.

### Docs site

`release.yml` calls the reusable `publish-docs.yml` workflow when `publish_docs`
is true (the default). The workflow builds `docs-site/dist`, syncs it to the S3
bucket behind `docs.kontext.tech`, invalidates CloudFront, and smoke-tests the
distribution. Dispatch `publish-docs.yml` directly for a docs-only change.

It needs the `AWS_DEPLOYMENT_ROLE_ARN_GLOBAL` secret and the `production`
environment. The S3 bucket, distribution, and Route53 record are defined in
`kontext-tech/kontext-platform` as `DocsCloudFrontStack`.

### TestPyPI

Dispatch `publish-pypi.yml` with `target=testpypi`. It derives a
`<version>.dev<run><attempt>` version so repeat uploads do not collide,
publishes, then reinstalls from TestPyPI and runs `kontext --help`.

Both indexes authenticate with PyPI trusted publishing (OIDC); no API token is
stored. The upload job must stay in this top-level workflow because PyPI does
not support reusable workflows as a trusted publisher. Both pending publishers
name `publish-pypi.yml` and use the matching `testpypi` / `pypi` environment;
both environments only allow deployments from `main`.

## Releasing the TypeScript packages

The `@kontext-tech/*` TypeScript packages are versioned in lockstep with
[Commitizen](https://commitizen-tools.github.io/commitizen/), configured under
`[tool.commitizen]` in the root `pyproject.toml`. There is no release PR step:
`release.yml` produces the bump, changelog, commit, and tag in one action, and
pushing the tag publishes.

### Bump and tag

`release.yml` runs `uv run cz bump` for you. To do the same locally:

```bash
pnpm run version:labs
git push --follow-tags
```

Do not use both paths for one release: `release.yml` always starts from
`origin/main`, so a local bump must be pushed before dispatching it.

That runs `uv run cz bump`, which:

1. Reads the Conventional Commits since the last `ts-packages-v*` tag.
2. Computes the next version and rewrites `version` in every
   `ts/*/package.json` file plus the root `package.json` (the `version_files`
   list). The root version is not cosmetic: `scripts/build-app-image.sh` reads
   it as `PUBLIC_KONTEXT_VERSION`.
3. Prepends the release notes to the root `CHANGELOG.md`.
4. Creates the `chore(release): version <old> -> <new>` commit and the
   `ts-packages-v<new>` tag.

Preview without changing anything:

```bash
uv run cz bump --dry-run --yes
```

Because `major_version_zero = true`, breaking changes still bump the **minor**
version while the project is pre-1.0. Force a specific increment when needed:

```bash
uv run cz bump --patch   # or --minor / --major / --prerelease
```

### Verify lockstep before publishing

```bash
pnpm run validate:workspace-versions
```

`tools/validate-workspace-versions.mjs` asserts that every package in the
`ts/*` workspace **and** the `py/*` workspace carries the same version, that the
root `package.json` and `[tool.commitizen]` agree with it, and that every package
is registered in `version_files`. It catches the one failure Commitizen cannot: a
version edited by hand, or a new `ts/*`/`py/*` package that was never added to
`version_files` (and so would be published unpinned). Pre-commit, CI, and the
publish workflow all run it, and the publish workflow additionally fails if the
pushed tag does not equal `ts-packages-v<root package.json version>`.

Both workspaces share the single `ts-packages-v$version` tag and the one
`[tool.commitizen] version`. `ts/schema` owns the OpenAPI contract and the
generated TypeScript API types, so both must always match the library version;
registering `py/*` in `version_files` is what keeps the Python distributions in
lockstep too.

### Legacy tags

Earlier releases used one tag per package (`@kontext-tech/<name>@<version>`), and
those tags anchor the published GitHub Releases from that era. They are **frozen
history**: the lockstep scheme deliberately replaced them with the single
`ts-packages-v<version>` tag, so they are no longer read by the release tooling.

Commitizen logs one `Invalid version tag` warning per legacy tag on every
changelog run because they do not match `tag_format`. The warnings are cosmetic —
`cz bump` resolves the last release from `ts-packages-v*` only — but they are
expected, not a signal that something is misconfigured.

Do not delete or retag the legacy tags without deciding what should happen to
the GitHub Releases they anchor. `git push --delete` is refused for a tag that
backs a published release, and one of them is the repository's current "Latest"
release.

### Publish

`publish-ts-packages.yml` triggers on `ts-packages-v*` — pushed by
`release.yml` or by `git push --follow-tags` — builds the shared packages, and
runs `pnpm --filter "./ts/*" publish` against `npm.pkg.github.com`.

The packages publish under the `@kontext-tech` scope, matching the repository
owner, so `publish-ts-packages.yml` uses the workflow `GITHUB_TOKEN` with
`packages: write` and needs no PAT. Consumers outside the org still need a
token with `read:packages` access.

Commitizen replaces the previous Changesets flow. The package versions were
normalized to a single lockstep version before the switch, because Commitizen
reads one configured version and writes it to every entry in `version_files`.

Commit message format is enforced on push by
`scripts/check-commitizen-branch.sh`, which runs `uv run cz check` over the
commits ahead of the base ref (see `.pre-commit-config.yaml`).
