import fs from "node:fs";
import path from "node:path";

import { repoRoot } from "./paths.mjs";

/**
 * Read `.env.docs.local` without exporting it to the whole process.
 *
 * The file is gitignored and only needed by `pnpm docs:record`. Values are not
 * printed anywhere.
 */
export function readDocsEnv() {
   const files = [".env.docs", ".env.docs.local"];
   const values = {};

   for (const name of files) {
      const file = path.join(repoRoot, name);
      if (!fs.existsSync(file)) continue;
      mergeFile(file, values);
   }

   return values;
}

function mergeFile(file, values) {
   for (const rawLine of fs.readFileSync(file, "utf8").split("\n")) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const eq = line.indexOf("=");
      if (eq <= 0) continue;
      const key = line.slice(0, eq).trim();
      let value = line.slice(eq + 1).trim();
      if (
         (value.startsWith('"') && value.endsWith('"')) ||
         (value.startsWith("'") && value.endsWith("'"))
      ) {
         value = value.slice(1, -1);
      }
      values[key] = value;
   }
}
