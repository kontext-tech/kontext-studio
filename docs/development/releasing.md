# Releasing

There are three independent release paths. They use separate triggers and
separate tag namespaces, so they never contend for the same GitHub Release.

| Artifact | Workflow | Trigger | Release tag |
| -------- | -------- | ------- | ----------- |
| Web app bundle (`app-dist-<version>.zip`) | `build-app.yml` | `push: tags: ["v*"]`, or `workflow_dispatch` | `v<version>` |
| Unified Python wheel (`kontext_labs-<version>-py3-none-any.whl`) | `release.yml` | `workflow_dispatch` only | `v<version>` |
| `@kontext-labs/*` TypeScript packages (GitHub Packages) | `publish-ts-packages.yml` | `push: tags: ["ts-packages-v*"]` | `ts-packages-v<version>` |

## Releasing a `v*` version

`build-app.yml` and `release.yml` share the `v<version>` tag, but they are
**complementary and explicitly ordered** — `build-app.yml` creates the release,
`release.yml` promotes it. They are deliberately not both wired to
`push: tags`, because running them concurrently on the same tag would race on
`gh release create`/`gh release edit` and on which assets exist when.

The sequence is:

1. Push a `v<version>` tag. `build-app.yml` builds the web app, creates the
   GitHub Release as a **draft**, and uploads `app-dist-<version>.zip`.
   (You can also run it manually with `workflow_dispatch`.)
2. Dispatch `release.yml` with `version=<version>` and
   `release_tag=v<version>`. It builds the unified wheel, uploads the wheel and
   `SHA256SUMS`, then flips the release to published (`--latest`, or
   `--prerelease` when that input is set).

`release.yml` verifies both that the built wheel's version matches the
`version` input and that `release_tag == "v" + version` before it touches the
release, so a typo fails the run instead of producing a mismatched release.

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

Commitizen replaces the previous Changesets flow. The package versions were
normalized to a single lockstep version before the switch, because Commitizen
reads one configured version and writes it to every entry in `version_files`.

Commit message format is enforced on push by
`scripts/check-commitizen-branch.sh`, which runs `uv run cz check` over the
commits ahead of the base ref (see `.pre-commit-config.yaml`).
