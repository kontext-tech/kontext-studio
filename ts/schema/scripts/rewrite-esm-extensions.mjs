#!/usr/bin/env node
/**
 * Post-build pass that makes the schema package's ESM output consumable by
 * native Node (both `import` and `require(esm)`).
 *
 * The schema is compiled with `moduleResolution: bundler`, which lets the
 * TypeScript source use extensionless relative imports (e.g. `./core`). That is
 * fine for bundlers but Node's ESM resolver rejects extensionless *directory*
 * imports with ERR_UNSUPPORTED_DIR_IMPORT. The `tsc-alias` pass only rewrites
 * the `@kontext-tech/schema/*` path aliases, leaving ~167 relative imports that
 * still point at directories or extensionless files.
 *
 * This script rewrites every relative import/export in dist/**​/*.js so that:
 *   - `./foo`           -> `./foo/index.js` (when dist/foo/index.js exists)
 *   - `../core`         -> `../core/index.js`
 *   - `./foo/bar`       -> `./foo/bar.js`   (when dist/foo/bar.js exists)
 * leaving already-correct `./foo.js` / `.json` specifiers untouched.
 */
import { readdirSync, readFileSync, writeFileSync, existsSync } from "fs";
import { dirname, join, relative, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = resolve(__dirname, "../dist");

/** Recursively list every file (relative to DIST_DIR) ending in the given suffix. */
function walk(dir, out = []) {
   for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full, out);
      else out.push(relative(DIST_DIR, full));
   }
   return out;
}

const files = walk(DIST_DIR);

/**
 * Resolve a relative specifier from a source file to an existing dist file.
 * Returns the rewritten specifier, or null when no rewrite is needed.
 */
function resolveSpec(fromFile, spec) {
   // Already a concrete file (has an extension) -> leave it.
   if (/\.(js|cjs|mjs|json)$/.test(spec)) return null;

   const base = resolve(DIST_DIR, dirname(fromFile));
   const target = resolve(base, spec);

   const candidates = [
      target + ".js",
      join(target, "index.js"),
      target + ".cjs",
      join(target, "index.cjs")
   ];
   for (const c of candidates) {
      if (existsSync(c)) {
         const rel = relative(resolve(DIST_DIR, dirname(fromFile)), c);
         return rel.startsWith(".") ? rel : "./" + rel;
      }
   }
   return null; // unresolved; leave as-is
}

let rewrites = 0;

// Matches the specifier in `from "./x"`, `import("./x")`, `export ... from "./x"`.
const specRe = /(["'])(\.\.?\/[^"']+)\1/g;

for (const relFile of files) {
   if (!relFile.endsWith(".js")) continue;
   const abs = join(DIST_DIR, relFile);
   const original = readFileSync(abs, "utf8");

   const text = original.replace(specRe, (match, quote, spec) => {
      const resolved = resolveSpec(relFile, spec);
      if (!resolved) return match;
      rewrites++;
      return `${quote}${resolved}${quote}`;
   });

   if (text !== original) writeFileSync(abs, text);
}

console.log(`✅ Rewrote ${rewrites} extensionless ESM specifiers in dist/`);
