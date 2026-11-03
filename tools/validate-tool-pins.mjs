import fs from "node:fs";
import path from "node:path";

// Keep tool versions that could be pinned in more than one place in lockstep.
//
// Ruff defines its version twice today, in two files owned by two different
// Dependabot ecosystems:
//
//   - the root `pyproject.toml` dev group pins an exact `ruff==X.Y.Z` (updated
//     through the `uv` ecosystem via `uv.lock`), and
//   - `.pre-commit-config.yaml` used to pin the matching
//     `astral-sh/ruff-pre-commit` `rev` (updated through the `pre-commit`
//     ecosystem).
//
// Nothing forces those two ecosystems to move together, and a drifted pin lets
// CI and pre-commit disagree about the same file. The fix is structural:
// pre-commit no longer pins ruff at all. Ruff runs through a local
// `language: system` hook that calls `uv run ruff`, exactly like the existing
// `pyright` hook, so `uv.lock` is the single source of truth and both CI and
// pre-commit execute the same binary.
//
// This script locks that decision in. It fails when:
//
//   1. ruff is not exact-pinned in the root dev dependency group,
//   2. ruff is re-pinned through a remote pre-commit repo (the drift-prone
//      design this replaced), or
//   3. the local `uv run ruff check` / `uv run ruff format` hooks disappear.
//
// It also guards the general case: any other tool that is exact-pinned in
// `pyproject.toml` *and* referenced by a remote pre-commit repo `rev` must
// agree on its version. There are none today; the check is here so the next one
// cannot drift silently.

const rootDir = process.cwd();
const pyprojectPath = path.join(rootDir, "pyproject.toml");
const preCommitPath = path.join(rootDir, ".pre-commit-config.yaml");

const violations = [];
const matches = [];

function readFile(filePath) {
   try {
      return fs.readFileSync(filePath, "utf8");
   } catch (error) {
      violations.push(`Failed to read ${path.relative(rootDir, filePath)}: ${error.message}`);
      return null;
   }
}

// Extract the body of a `[section]` table so a `==` pin in another table (for
// example an optional-dependency extra) is not mistaken for the tool contract.
function tomlSection(source, header) {
   const lines = source.split(/\r?\n/);
   const start = lines.findIndex((line) => line.trim() === header);
   if (start === -1) {
      return "";
   }

   const body = [];
   for (let index = start + 1; index < lines.length; index += 1) {
      if (/^\s*\[/.test(lines[index])) {
         break;
      }
      body.push(lines[index]);
   }
   return body.join("\n");
}

// Exact `name==version` pins from the root dev dependency group.
function readExactPins(source) {
   const pins = new Map();
   const pattern = /^\s*"([A-Za-z0-9_.-]+)==([^"\s,]+)"/gm;
   let match;
   while ((match = pattern.exec(tomlSection(source, "[dependency-groups]"))) !== null) {
      pins.set(match[1].toLowerCase(), match[2]);
   }
   return pins;
}

// Remote pre-commit repositories and their `rev`. A `rev` is only read from the
// repository block it follows, so a hook-level key cannot masquerade as a
// version.
function readPreCommitRepos(source) {
   const repos = [];
   let current = null;
   for (const line of source.split(/\r?\n/)) {
      const repo = line.match(/^\s*-\s*repo:\s*(\S+?)\s*$/);
      if (repo) {
         current = { repo: repo[1], rev: null };
         repos.push(current);
         continue;
      }
      const rev = line.match(/^\s*rev:\s*(\S+?)\s*$/);
      if (rev && current && current.rev === null) {
         current.rev = rev[1];
      }
   }
   return repos;
}

function repoSlug(repo) {
   return repo.replace(/\.git$/, "").split("/").pop().toLowerCase();
}

// A pre-commit mirror repo is conventionally named `<tool>-pre-commit`, so both
// the full slug and the de-suffixed name are candidate dependency names.
function candidateTools(repo) {
   const slug = repoSlug(repo);
   return slug.endsWith("-pre-commit") ? [slug, slug.slice(0, -"-pre-commit".length)] : [slug];
}

function normalizeRev(rev) {
   return rev.replace(/^v/, "");
}

const pyproject = readFile(pyprojectPath);
const preCommit = readFile(preCommitPath);

if (pyproject !== null && preCommit !== null) {
   const pins = readExactPins(pyproject);
   const repos = readPreCommitRepos(preCommit);

   const ruffPin = pins.get("ruff");
   if (!ruffPin) {
      violations.push(
         "Root pyproject.toml must pin an exact `ruff==<version>` in [dependency-groups].dev.",
      );
   }

   const remoteRuff = repos.find((entry) => repoSlug(entry.repo) === "ruff-pre-commit");
   if (remoteRuff) {
      violations.push(
         `Ruff must not be pinned through a remote pre-commit repo (${remoteRuff.repo}@${
            remoteRuff.rev ?? "?"
         }); run it through a local 'uv run ruff' hook so pyproject.toml/uv.lock stays the only source of truth.`,
      );
   }

   const runsRuffCheck = /^\s*entry:.*\buv run\b.*\bruff check\b/m.test(preCommit);
   const runsRuffFormat = /^\s*entry:.*\buv run\b.*\bruff format\b/m.test(preCommit);
   if (ruffPin && (!runsRuffCheck || !runsRuffFormat)) {
      const missing = [
         !runsRuffCheck ? "'uv run ruff check'" : null,
         !runsRuffFormat ? "'uv run ruff format'" : null,
      ].filter(Boolean);
      violations.push(
         `Missing local pre-commit hook(s) for ruff: expected ${missing.join(" and ")}.`,
      );
   }

   // Cross-file parity for any other tool that remains pinned in both places.
   for (const entry of repos) {
      if (entry.repo === "local" || entry.rev === null) {
         continue;
      }
      const pinName = candidateTools(entry.repo).find((candidate) => pins.has(candidate));
      if (!pinName || pinName === "ruff") {
         continue;
      }

      const pin = pins.get(pinName);
      matches.push(
         `${pinName}: pyproject.toml ${pin} vs .pre-commit-config.yaml ${entry.repo}@${entry.rev}`,
      );
      if (normalizeRev(entry.rev) !== pin) {
         violations.push(
            `Tool '${pinName}' is pinned twice with different versions: pyproject.toml has ` +
               `${pin} but .pre-commit-config.yaml pins rev ${entry.rev}.`,
         );
      }
   }
}

if (violations.length > 0) {
   console.error("Tool pin validation failed:");
   for (const violation of violations) {
      console.error(`- ${violation}`);
   }
   process.exit(1);
}

for (const match of matches) {
   console.log(`Cross-file pin parity ok - ${match}`);
}
console.log("Tool pin validation passed: ruff is pinned once in pyproject.toml and runs via `uv run ruff`.");
