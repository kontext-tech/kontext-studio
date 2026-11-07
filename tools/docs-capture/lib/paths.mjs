import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

export const repoRoot = path.resolve(here, "..", "..", "..");
export const docsDir = path.join(repoRoot, "docs");
export const guideDir = path.join(docsDir, "user-guide");
export const assetsDir = path.join(guideDir, "assets");
export const toolsDir = path.join(repoRoot, "tools", "docs-capture");
export const inventoryFile = path.join(toolsDir, "inventory.generated.json");
export const mediaManifestFile = path.join(toolsDir, "media.generated.json");
export const routesSource = path.join(repoRoot, "app", "src", "routing", "routes.ts");
export const routeTypesSource = path.join(
   repoRoot,
   "app",
   "src",
   "types",
   "routeTypes.ts"
);
export const appDist = path.join(repoRoot, "app", "dist");
