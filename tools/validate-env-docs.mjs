import fs from "node:fs";
import path from "node:path";

// Drift guard for docs/development/environment.md.
//
// The page is the human reference; the actual sources of truth are
// .env.example, the ALL_ENV_VARS registry, and environment reads in code.
// This check fails when a runtime variable is undocumented or a documented
// name no longer exists.

const rootDir = process.cwd();
const docPath = path.join(rootDir, "docs", "development", "environment.md");
const envExamplePath = path.join(rootDir, ".env.example");
const registryPath = path.join(
   rootDir,
   "py/kontext-common/src/kontext/common/constants/env_vars.py"
);

// Names read through a module-level constant rather than an os.getenv literal.
const KNOWN_CONSTANT_VARS = new Set([
   "CORS_ALLOWED_ORIGINS",
   "KONTEXT_ALLOWED_HOSTS",
   "KONTEXT_DISABLED_SITE_FEATURES",
   "KONTEXT_INTERNAL_API_URL",
   "KONTEXT_JWT_AUDIENCE",
   "KONTEXT_JWT_ISSUER",
   "KONTEXT_JWT_SECRET_KEY",
   "KONTEXT_LOCAL_CONSOLE_AUTO_AUTH",
   "KONTEXT_LOCAL_LAUNCH_TOKEN",
   "KONTEXT_LOCAL_MODE",
   "KONTEXT_LOG_FORMAT",
   "KONTEXT_LOG_LEVEL",
   "KONTEXT_PARENT_PID",
   "KONTEXT_PROJECT_DB_URL",
   "KONTEXT_PYTHON_RUNTIME_WHEELHOUSE",
   "KONTEXT_PROJECT_PERMISSION_MAP_PATH",
   "KONTEXT_SITE_FEATURES",
   "LOG_FORMAT",
   "LOG_LEVEL",
   "PROJECT_PERMISSION_MAP_PATH"
]);

// Third-party credentials live in the provider documentation; tooling names
// are build/capture internals, not runtime configuration.
const IGNORED = [
   /^(OPENAI|ANTHROPIC|AZURE|GOOGLE|GEMINI|MISTRAL|DEEPSEEK|OPENROUTER|OLLAMA|LM_STUDIO|BEDROCK|AWS)_/,
   /^DOCS_/,
   /^(ANALYZE|NODE_ENV|UV_CACHE_DIR|VITE_MODE|WINDIR)$/,
   /^KONTEXT_[A-Z0-9_]*OUT_FILE$/
];

const SKIP_DIRS = new Set([
   ".git",
   ".venv",
   "__pycache__",
   "dist",
   "node_modules",
   "tests",
   "test",
   "_app_dist"
]);

function isIgnored(name) {
   return IGNORED.some((pattern) => pattern.test(name));
}

function documentedNames() {
   const names = new Set();
   for (const line of fs.readFileSync(docPath, "utf8").split("\n")) {
      const cells = line.split("|");
      if (cells.length < 2) continue;
      const firstCell = cells[1];
      for (const match of firstCell.matchAll(/`([A-Z][A-Z0-9_]+)`/g)) {
         names.add(match[1]);
      }
   }
   return names;
}

function envExampleNames() {
   const names = new Set();
   for (const line of fs.readFileSync(envExamplePath, "utf8").split("\n")) {
      const match = /^\s*#?\s*([A-Z][A-Z0-9_]+)=/.exec(line);
      if (match) names.add(match[1]);
   }
   return names;
}

function registryNames() {
   const names = new Set();
   for (const match of fs
      .readFileSync(registryPath, "utf8")
      .matchAll(/=\s*"([A-Z][A-Z0-9_]+)"/g)) {
      names.add(match[1]);
   }
   return names;
}

function walk(directory, results = []) {
   for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (SKIP_DIRS.has(entry.name)) continue;
      const fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
         walk(fullPath, results);
      } else if (/\.(py|ts|tsx|mjs|js|cjs)$/.test(entry.name)) {
         results.push(fullPath);
      }
   }
   return results;
}

function codeNames() {
   const names = new Set();
   const patterns = [
      /os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']/g,
      /os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]+)["']/g,
      /os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']/g,
      /process\.env\.([A-Z][A-Z0-9_]+)/g,
      /process\.env\[\s*["']([A-Z][A-Z0-9_]+)["']/g,
      /getEnvVar\(\s*["']([A-Z][A-Z0-9_]+)["']/g
   ];

   for (const root of ["py", "tools", "app", "ts", "docs-site"]) {
      const absolute = path.join(rootDir, root);
      if (!fs.existsSync(absolute)) continue;
      for (const file of walk(absolute)) {
         const text = fs.readFileSync(file, "utf8");
         for (const pattern of patterns) {
            for (const match of text.matchAll(pattern)) {
               names.add(match[1]);
            }
         }
      }
   }
   return names;
}

const documented = documentedNames();
const expected = new Set(
   [
      ...envExampleNames(),
      ...registryNames(),
      ...codeNames(),
      ...KNOWN_CONSTANT_VARS
   ].filter((name) => !isIgnored(name))
);

const missing = [...expected].filter((name) => !documented.has(name)).sort();
const unknown = [...documented].filter((name) => !expected.has(name)).sort();

const problems = [];
if (missing.length > 0) {
   problems.push(
      `Undocumented runtime variables (${missing.length}):\n  ${missing.join("\n  ")}`
   );
}
if (unknown.length > 0) {
   problems.push(
      `Documented names not found in code, .env.example, or the registry (${unknown.length}):\n  ${unknown.join("\n  ")}`
   );
}

if (problems.length > 0) {
   console.error(problems.join("\n\n"));
   console.error(
      "\nUpdate docs/development/environment.md, or the source if the variable is stale."
   );
   process.exit(1);
}

console.log(
   `Environment docs are in sync (${documented.size} variables documented).`
);
