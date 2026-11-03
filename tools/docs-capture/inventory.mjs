#!/usr/bin/env node
/**
 * Refresh or verify `inventory.generated.json`.
 *
 *   node tools/docs-capture/inventory.mjs           # write the file
 *   node tools/docs-capture/inventory.mjs --check   # fail when it is stale
 */
import fs from "node:fs";

import { buildInventory, serializeInventory } from "./lib/inventory.mjs";
import { inventoryFile } from "./lib/paths.mjs";

const check = process.argv.includes("--check");
const next = serializeInventory(buildInventory());

if (check) {
   const current = fs.existsSync(inventoryFile)
      ? fs.readFileSync(inventoryFile, "utf8")
      : "";
   if (current !== next) {
      console.error(
         "inventory.generated.json is stale. Run `pnpm docs:inventory` and commit the result."
      );
      process.exit(1);
   }
   console.log(`Route inventory is current (${buildInventory().routeCount} routes).`);
} else {
   fs.writeFileSync(inventoryFile, next);
   const { routeCount } = buildInventory();
   console.log(`Wrote ${inventoryFile} (${routeCount} routes).`);
}
