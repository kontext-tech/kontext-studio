import fs from "node:fs";
import path from "node:path";

// The lockstep version contract for the `@kontext-tech/*` TypeScript packages.
//
// Versioning is driven by Commitizen (`uv run cz bump`), configured in the root
// `pyproject.toml` under `[tool.commitizen]`. Commitizen rewrites every entry in
// `version_files` to a single new version and creates the `ts-packages-v*` tag
// that triggers `.github/workflows/publish-ts-packages.yml`.
//
// This script asserts that the working tree matches that contract before a
// publish runs. It catches the failure mode Commitizen cannot: a hand-edited
// `package.json` version, or a package added to `ts/` without being registered
// in `version_files`, either of which would publish an inconsistent package set.

const rootDir = process.cwd();
const tsRoot = path.join(rootDir, "ts");
const rootPackageJsonPath = path.join(rootDir, "package.json");
const pyprojectPath = path.join(rootDir, "pyproject.toml");
const versionPattern = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

const violations = [];

function readJson(filePath) {
   try {
      return JSON.parse(fs.readFileSync(filePath, "utf8"));
   } catch (error) {
      violations.push(`Failed to parse ${path.relative(rootDir, filePath)}: ${error.message}`);
      return null;
   }
}

// Extract `version` and the `version_files` array from the `[tool.commitizen]`
// table. Splitting on section headers avoids lookahead/`\Z` portability issues
// between Python and JavaScript regex engines.
function readCommitizenConfig() {
   let source;

   try {
      source = fs.readFileSync(pyprojectPath, "utf8");
   } catch (error) {
      violations.push(`Failed to read pyproject.toml: ${error.message}`);
      return { version: null, versionFiles: [] };
   }

   const sectionPattern = /^\[([^\]]+)\][ \t]*$/gm;
   const headers = [...source.matchAll(sectionPattern)].map((match) => ({
      name: match[1],
      start: match.index,
      end: match.index + match[0].length
   }));

   const target = headers.find((header) => header.name === "tool.commitizen");

   if (!target) {
      violations.push("pyproject.toml is missing a [tool.commitizen] table");
      return { version: null, versionFiles: [] };
   }

   const next = headers.find((header) => header.start > target.start);
   const table = source.slice(target.end, next ? next.start : source.length);

   const versionMatch = table.match(/^[ \t]*version[ \t]*=[ \t]*"([^"]+)"/m);

   if (!versionMatch) {
      violations.push("[tool.commitizen] is missing a version entry");
   }

   const versionFilesMatch = table.match(/^[ \t]*version_files[ \t]*=[ \t]*\[([\s\S]*?)\]/m);

   if (!versionFilesMatch) {
      violations.push("[tool.commitizen] is missing a version_files array");
      return { version: versionMatch?.[1] ?? null, versionFiles: [] };
   }

   const versionFiles = [...versionFilesMatch[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]);

   return { version: versionMatch?.[1] ?? null, versionFiles };
}

const { version: commitizenVersion, versionFiles } = readCommitizenConfig();

// Map every `version_files` entry to a package directory so the registered set
// can be compared against what actually exists on disk. Two workspaces share the
// same lockstep version: `ts/*` npm packages and `py/*` uv packages.
const registeredDirs = new Set();
const registeredPythonDirs = new Set();
let rootRegistered = false;
let appRegistered = false;

for (const entry of versionFiles) {
   const [filePath, pointer] = entry.split(":");

   if (pointer !== "version") {
      violations.push(
         `version_files entry "${entry}" targets "${pointer ?? "(none)"}"; only "version" is supported`
      );
      continue;
   }

   if (filePath === "package.json") {
      rootRegistered = true;

      if (!fs.existsSync(path.join(rootDir, filePath))) {
         violations.push(`version_files entry "${entry}" points at a missing file`);
      }

      continue;
   }

   const isAppPackage = filePath === "app/package.json";
   const isTsPackage = filePath.startsWith("ts/") && filePath.endsWith("/package.json");
   const isPyPackage = filePath.startsWith("py/") && filePath.endsWith("/pyproject.toml");

   if (isAppPackage) {
      appRegistered = true;

      if (!fs.existsSync(path.join(rootDir, filePath))) {
         violations.push(`version_files entry "${entry}" points at a missing file`);
      }

      continue;
   }

   if (!isTsPackage && !isPyPackage) {
      violations.push(
         `version_files entry "${entry}" is outside the ts/*/package.json or py/*/pyproject.toml contract`
      );
      continue;
   }

   if (isTsPackage) {
      registeredDirs.add(filePath.split("/")[1]);
   } else {
      registeredPythonDirs.add(filePath.split("/")[1]);
   }

   if (!fs.existsSync(path.join(rootDir, filePath))) {
      violations.push(`version_files entry "${entry}" points at a missing file`);
   }
}

if (!rootRegistered) {
   violations.push(
      "package.json is not registered in [tool.commitizen].version_files; scripts/build-app-image.sh reads its version as PUBLIC_KONTEXT_VERSION"
   );
}

const packageDirs = fs
   .readdirSync(tsRoot, { withFileTypes: true })
   .filter((entry) => entry.isDirectory())
   .map((entry) => entry.name)
   .filter((dir) => fs.existsSync(path.join(tsRoot, dir, "package.json")))
   .sort();

if (commitizenVersion !== null && !versionPattern.test(commitizenVersion)) {
   violations.push(`[tool.commitizen] version "${commitizenVersion}" is not a semver version`);
}

const versionsByDir = new Map();

for (const dir of packageDirs) {
   const relativePath = `ts/${dir}/package.json`;
   const packageJson = readJson(path.join(tsRoot, dir, "package.json"));

   if (!packageJson) {
      continue;
   }

   if (typeof packageJson.version !== "string" || !versionPattern.test(packageJson.version)) {
      violations.push(
         `${relativePath} has an invalid or missing version (${JSON.stringify(packageJson.version)})`
      );
      continue;
   }

   versionsByDir.set(dir, packageJson.version);

   if (!registeredDirs.has(dir)) {
      violations.push(
         `${relativePath} is not registered in [tool.commitizen].version_files, so \`cz bump\` will not update it`
      );
   }
}

for (const dir of registeredDirs) {
   if (!versionsByDir.has(dir)) {
      violations.push(`[tool.commitizen].version_files references ts/${dir}, which has no ts/${dir}/package.json`);
   }
}

const distinctVersions = new Set(versionsByDir.values());

if (distinctVersions.size > 1) {
   const detail = [...versionsByDir.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([dir, version]) => `${dir}=${version}`)
      .join(", ");

   violations.push(`ts/* packages are not in lockstep (expected a single version): ${detail}`);
}

const packageVersion = distinctVersions.size === 1 ? [...distinctVersions][0] : null;

if (packageVersion !== null && commitizenVersion !== null && packageVersion !== commitizenVersion) {
   violations.push(
      `[tool.commitizen] version (${commitizenVersion}) does not match the ts/* package version (${packageVersion})`
   );
}

// `pnpm install --frozen-lockfile` runs before publishing, so a stale root
// version is the usual symptom of a hand-rolled bump.
const rootPackageJson = readJson(rootPackageJsonPath);

if (rootPackageJson && commitizenVersion !== null && rootPackageJson.version !== commitizenVersion) {
   violations.push(
      `package.json version (${JSON.stringify(rootPackageJson.version)}) does not match [tool.commitizen] version (${commitizenVersion})`
   );
}

// `app` is a pnpm workspace member but is not a published package. Nothing reads
// its version, so it drifts unless `cz bump` writes it too: keep it registered in
// `version_files` so "the workspace version" has one meaning.
const appPackageJsonPath = path.join(rootDir, "app", "package.json");

if (fs.existsSync(appPackageJsonPath)) {
   const appPackageJson = readJson(appPackageJsonPath);

   if (!appRegistered) {
      violations.push(
         "app/package.json is not registered in [tool.commitizen].version_files, so `cz bump` will not update it"
      );
   }

   if (appPackageJson && commitizenVersion !== null && appPackageJson.version !== commitizenVersion) {
      violations.push(
         `app/package.json version (${JSON.stringify(appPackageJson.version)}) does not match [tool.commitizen] version (${commitizenVersion})`
      );
   }
}

// The Python workspace mirrors the same lockstep contract. `ts/schema` drives the
// generated Pydantic models, so a hand-rolled bump or a new `py/kontext-*`
// package that is not registered would also break parity.
const pyRoot = path.join(rootDir, "py");
const pyVersionPattern = /^\s*version\s*=\s*"([^"]+)"/m;

const pyPackageDirs = fs.existsSync(pyRoot)
   ? fs
        .readdirSync(pyRoot, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
        .filter((dir) => fs.existsSync(path.join(pyRoot, dir, "pyproject.toml")))
        .sort()
   : [];

const pyVersionsByDir = new Map();

function readPyprojectVersion(filePath) {
   try {
      return fs.readFileSync(filePath, "utf8").match(pyVersionPattern)?.[1] ?? null;
   } catch {
      return null;
   }
}

for (const dir of pyPackageDirs) {
   const relativePath = `py/${dir}/pyproject.toml`;
   const version = readPyprojectVersion(path.join(pyRoot, dir, "pyproject.toml"));

   if (version === null || !versionPattern.test(version)) {
      violations.push(
         `${relativePath} has an invalid or missing version (${JSON.stringify(version)})`
      );
      continue;
   }

   pyVersionsByDir.set(dir, version);

   if (!registeredPythonDirs.has(dir)) {
      violations.push(
         `${relativePath} is not registered in [tool.commitizen].version_files, so \`cz bump\` will not update it`
      );
   }
}

for (const dir of registeredPythonDirs) {
   if (!pyVersionsByDir.has(dir)) {
      violations.push(
         `[tool.commitizen].version_files references py/${dir}, which has no py/${dir}/pyproject.toml`
      );
   }
}

const distinctPyVersions = new Set(pyVersionsByDir.values());

if (distinctPyVersions.size > 1) {
   const detail = [...pyVersionsByDir.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([dir, version]) => `${dir}=${version}`)
      .join(", ");

   violations.push(`py/* packages are not in lockstep (expected a single version): ${detail}`);
}

const pyPackageVersion = distinctPyVersions.size === 1 ? [...distinctPyVersions][0] : null;

if (pyPackageVersion !== null && commitizenVersion !== null && pyPackageVersion !== commitizenVersion) {
   violations.push(
      `[tool.commitizen] version (${commitizenVersion}) does not match the py/* package version (${pyPackageVersion})`
   );
}

if (violations.length > 0) {
   console.error("Workspace version validation failed:\n");
   for (const violation of violations) {
      console.error(`- ${violation}`);
   }
   console.error("\nRun `pnpm run version:labs` (`uv run cz bump`) to update all versions together.");
   process.exit(1);
}

console.log(
   `Workspace version validation passed: ${versionsByDir.size} ts/* packages and ${pyVersionsByDir.size} py/* packages at ${packageVersion} (tag prefix ts-packages-v).`
);
