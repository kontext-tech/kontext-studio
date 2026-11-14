#!/usr/bin/env node
// Build the Windows installer with Tauri's NSIS bundler and copy it into
// dist/ under the release naming convention. Tauri's config targets "app"
// (a macOS-only bundle type), so the bundler is selected through --bundles.
import { execSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));

const conf = JSON.parse(
   readFileSync(join(ROOT, "desktop/src-tauri/tauri.conf.json"), "utf8")
);

execSync(
   "pnpm exec tauri build --config desktop/src-tauri/tauri.conf.json --bundles nsis",
   { stdio: "inherit", cwd: ROOT }
);

const bundleDir = join(ROOT, "desktop/src-tauri/target/release/bundle/nsis");
const installers = readdirSync(bundleDir).filter((name) =>
   name.endsWith("-setup.exe")
);
if (installers.length === 0) {
   console.error(`No NSIS installer found in ${bundleDir}`);
   process.exit(1);
}

const outDir = join(ROOT, "dist");
mkdirSync(outDir, { recursive: true });
const distName = `Kontext-Studio-${conf.version}-Windows-x64.exe`;
copyFileSync(join(bundleDir, installers[0]), join(outDir, distName));
console.log(`Created dist/${distName}`);
