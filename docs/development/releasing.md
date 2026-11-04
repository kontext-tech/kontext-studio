# Releasing

There are three release artifacts. They use separate triggers and tag
namespaces, so they never contend for the same GitHub Release. The docs site
piggybacks on the `v<version>` release and has no tag of its own.

| Artifact | Workflow | Trigger | Release tag |
| -------- | -------- | ------- | ----------- |
| Unified Python wheel (`kontext_labs-<version>-py3-none-any.whl`) | `publish-pypi.yml` | `workflow_dispatch` only | `v<version>` (GitHub Release + PyPI) |
| `@kontext-labs/*` TypeScript packages (GitHub Packages) | `publish-ts-packages.yml` | `push: tags: ["ts-packages-v*"]` | `ts-packages-v<version>` |
| Docs site (`docs.kontext.tech`) | `publish-docs.yml` | `workflow_call` from `release.yml`, or `workflow_dispatch` | none |

## Releasing a `v<version>` version

The unified wheel is built once, by `publish-pypi.yml`. `release.yml` only
creates or promotes the GitHub Release, so the two dispatch steps are
deliberately ordered: the release exists before anything reaches PyPI.

1. Dispatch `release.yml` with `version=<version>` and
   `release_tag=v<version>`. It validates `release_tag == "v" + version`, then
   creates the release (the tag is created from the dispatched commit if it
   does not exist) or promotes an existing one (`--latest`, or `--prerelease`
   when that input is set). Unless `publish_docs` is false, it then publishes
   the docs site.
2. Dispatch `publish-pypi.yml` with `target=pypi`, `version=<version>`, and
   `confirm=<version>`. It builds the wheel, verifies its version, writes
   `SHA256SUMS`, smoke-tests both CLI entry points, publishes to PyPI, then
   attaches the wheel and `SHA256SUMS` to the release.

`publish-pypi.yml` refuses a production publish when `version` differs from the
workspace version or `confirm` differs from `version`, so a typo fails the run
instead of publishing the wrong artifact.

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
publishes, then reinstalls from TestPyPI and runs `kontext-labs --help`.

Both indexes authenticate with PyPI trusted publishing (OIDC); no API token is
stored. The upload job must stay in this top-level workflow because PyPI does
not support reusable workflows as a trusted publisher. Both pending publishers
name `publish-pypi.yml` and use the matching `testpypi` / `pypi` environment;
both environments only allow deployments from `main`.

## Releasing the TypeScript packages

The `@kontext-labs/*` TypeScript packages are versioned in lockstep with
[Commitizen](https://commitizen-tools.github.io/commitizen/), configured under
`[tool.commitizen]` in the root `pyproject.toml`. There is no release PR step:
the version bump, changelog, commit, and tag are all produced locally by one
command, and pushing the tag publishes.

### Bump and tag

```bash
pnpm run version:labs
```

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

Earlier releases used one tag per package (`@kontext-labs/<name>@<version>`), and
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

```bash
git push --follow-tags
```

`publish-ts-packages.yml` triggers on `ts-packages-v*`, builds the shared
packages, and runs `pnpm --filter "./ts/*" publish` against
`npm.pkg.github.com`.

The packages keep the `@kontext-labs` scope while the repository lives under
`kontext-tech`. Publishing therefore needs `KONTEXT_PACKAGES_TOKEN`, a PAT with
`write:packages` access to the account that owns that scope; the workflow's
`GITHUB_TOKEN` only covers the `kontext-tech` owner. Renaming the scope to
`@kontext-tech` is a breaking change for consumers and must update every
package name together with `setup-node.scope` in the workflow.

Commitizen replaces the previous Changesets flow. The package versions were
normalized to a single lockstep version before the switch, because Commitizen
reads one configured version and writes it to every entry in `version_files`.

Commit message format is enforced on push by
`scripts/check-commitizen-branch.sh`, which runs `uv run cz check` over the
commits ahead of the base ref (see `.pre-commit-config.yaml`).
