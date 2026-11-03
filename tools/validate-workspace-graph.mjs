import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const rootDir = process.cwd();
const tsRoot = path.join(rootDir, "ts");
const require = createRequire(import.meta.url);

const referenceAllowlist = new Map([["site", new Set()]]);

function loadTypeScript() {
   const candidates = [
      () => require("typescript"),
      () => require(path.join(rootDir, "node_modules", "typescript")),
      () => require(path.join(path.dirname(rootDir), "node_modules", "typescript"))
   ];

   for (const candidate of candidates) {
      try {
         return candidate();
      } catch {
         continue;
      }
   }

   return null;
}

const ts = loadTypeScript();

function parseJsonc(filePath) {
   if (ts) {
      const raw = fs.readFileSync(filePath, "utf8");
      const parsed = ts.parseConfigFileTextToJson(filePath, raw);

      if (parsed.error) {
         const message = ts.flattenDiagnosticMessageText(
            parsed.error.messageText,
            "\n"
         );
         throw new Error(`Failed to parse ${filePath}: ${message}`);
      }

      return parsed.config ?? {};
   }

   const raw = fs.readFileSync(filePath, "utf8");
   const withoutBlockComments = raw.replace(/\/\*[\s\S]*?\*\//g, "");
   const withoutLineComments = withoutBlockComments.replace(/^\s*\/\/.*$/gm, "");
   const withoutTrailingCommas = withoutLineComments.replace(/,(\s*[}\]])/g, "$1");
   return JSON.parse(withoutTrailingCommas);
}

const packageDirs = fs
   .readdirSync(tsRoot, { withFileTypes: true })
   .filter((entry) => entry.isDirectory())
   .map((entry) => entry.name)
   .filter((dir) => {
      return (
         fs.existsSync(path.join(tsRoot, dir, "package.json")) &&
         fs.existsSync(path.join(tsRoot, dir, "tsconfig.json"))
      );
   });

const packages = new Map();
const dirByPackageName = new Map();

for (const dir of packageDirs) {
   const packageJsonPath = path.join(tsRoot, dir, "package.json");
   const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

   packages.set(dir, {
      dir,
      name: packageJson.name,
      packageJson,
      tsconfigPath: path.join(tsRoot, dir, "tsconfig.json")
   });
   dirByPackageName.set(packageJson.name, dir);
}

function detectCycles(graph) {
   const visiting = new Set();
   const visited = new Set();
   const stack = [];
   const cycles = [];

   const walk = (node) => {
      visiting.add(node);
      stack.push(node);

      for (const dependency of graph.get(node) ?? []) {
         if (!graph.has(dependency)) {
            continue;
         }

         if (!visiting.has(dependency) && !visited.has(dependency)) {
            walk(dependency);
            continue;
         }

         if (visiting.has(dependency)) {
            const cycleStart = stack.indexOf(dependency);
            cycles.push([...stack.slice(cycleStart), dependency]);
         }
      }

      stack.pop();
      visiting.delete(node);
      visited.add(node);
   };

   for (const node of graph.keys()) {
      if (!visited.has(node)) {
         walk(node);
      }
   }

   return cycles;
}

const dependencyGraph = new Map();
const referenceGraph = new Map();
const violations = [];

for (const pkg of packages.values()) {
   const dependencyDirs = new Set(
      Object.keys(pkg.packageJson.dependencies ?? {})
         .filter((dependencyName) => dirByPackageName.has(dependencyName))
         .map((dependencyName) => dirByPackageName.get(dependencyName))
   );

   dependencyGraph.set(pkg.dir, [...dependencyDirs].sort());

   const tsconfig = parseJsonc(pkg.tsconfigPath);
   const referencedDirs = new Set(
      (tsconfig.references ?? [])
         .map((reference) => path.basename(path.normalize(reference.path)))
         .filter((referenceDir) => packages.has(referenceDir))
   );

   referenceGraph.set(pkg.dir, [...referencedDirs].sort());

   const allowedExtraReferences = referenceAllowlist.get(pkg.dir) ?? new Set();

   const missingReferences = [...dependencyDirs]
      .filter((dependencyDir) => !referencedDirs.has(dependencyDir))
      .sort();
   const extraReferences = [...referencedDirs]
      .filter(
         (referenceDir) =>
            !dependencyDirs.has(referenceDir) &&
            !allowedExtraReferences.has(referenceDir)
      )
      .sort();

   if (missingReferences.length > 0) {
      violations.push(
         `${pkg.name} is missing tsconfig references for: ${missingReferences
            .map((dir) => packages.get(dir)?.name ?? dir)
            .join(", ")}`
      );
   }

   if (extraReferences.length > 0) {
      violations.push(
         `${pkg.name} has extra tsconfig references without runtime dependencies: ${extraReferences
            .map((dir) => packages.get(dir)?.name ?? dir)
            .join(", ")}`
      );
   }
}

const dependencyCycles = detectCycles(dependencyGraph);
const referenceCycles = detectCycles(referenceGraph);

for (const cycle of dependencyCycles) {
   violations.push(
      `Workspace dependency cycle detected: ${cycle
         .map((dir) => packages.get(dir)?.name ?? dir)
         .join(" -> ")}`
   );
}

for (const cycle of referenceCycles) {
   violations.push(
      `TypeScript reference cycle detected: ${cycle
         .map((dir) => packages.get(dir)?.name ?? dir)
         .join(" -> ")}`
   );
}

if (violations.length > 0) {
   console.error("Workspace graph validation failed:\n");
   for (const violation of violations) {
      console.error(`- ${violation}`);
   }
   process.exit(1);
}

console.log(
   `Workspace graph validation passed for ${packages.size} shared packages.`
);
