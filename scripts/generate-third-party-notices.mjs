#!/usr/bin/env node
/**
 * Regenerate THIRD_PARTY_NOTICES.md from the committed lockfiles.
 *
 * Run before a release, after dependency updates:
 *   node scripts/generate-third-party-notices.mjs
 */
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const run = (command, args) =>
   execFileSync(command, args, {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024
   });

const npmByLicense = JSON.parse(
   run("pnpm", ["licenses", "list", "--prod", "--json"])
);
const npmPackages = [];
for (const [license, packages] of Object.entries(npmByLicense)) {
   for (const pkg of packages) {
      npmPackages.push({
         name: pkg.name,
         version: (pkg.versions ?? []).join(", "),
         license
      });
   }
}
npmPackages.sort((a, b) => a.name.localeCompare(b.name));

const exported = run("uv", [
   "export",
   "--frozen",
   "--no-dev",
   "--no-hashes",
   "--no-emit-project"
]);
const runtimeNames = new Set(
   exported
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#") && !line.startsWith("-"))
      .map((line) =>
         line
            .split(/[=;<>\s]/)[0]
            .toLowerCase()
            .replaceAll("_", "-")
      )
);

const pythonPackages = JSON.parse(
   run("uv", [
      "run",
      "--with",
      "pip-licenses",
      "pip-licenses",
      "--format=json",
      "--with-urls"
   ])
)
   .filter((pkg) =>
      runtimeNames.has(String(pkg.Name).toLowerCase().replaceAll("_", "-"))
   )
   .map((pkg) => ({
      name: pkg.Name,
      version: pkg.Version,
      license: pkg.License,
      url: pkg.URL
   }))
   .sort((a, b) => a.name.localeCompare(b.name));

const rows = (packages, withUrl) =>
   packages
      .map(
         (pkg) =>
            `| ${pkg.name} | ${pkg.version} | ${String(pkg.license).replaceAll("|", "\\|")} |${
               withUrl ? ` ${pkg.url ? `<${pkg.url}>` : ""} |` : ""
            }`
      )
      .join("\n");

const content = `# Third-party notices

Kontext Studio is MIT licensed. This file lists the third-party packages it uses
and their licenses. It is generated from the committed lockfiles by
\`node scripts/generate-third-party-notices.mjs\`; do not hand-edit it.

Regenerate it after dependency updates and before a release.

## Frontend packages

Production npm dependencies across the workspace:

| Package | Version | License |
| --- | --- | --- |
${rows(npmPackages, false)}

## Python packages

Runtime Python dependencies of the unified \`kontext-studio\` wheel:

| Package | Version | License | URL |
| --- | --- | --- | --- |
${rows(pythonPackages, true)}
`;

writeFileSync("THIRD_PARTY_NOTICES.md", content);
console.log(
   `Wrote THIRD_PARTY_NOTICES.md (${npmPackages.length} npm, ${pythonPackages.length} Python packages)`
);
