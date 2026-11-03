#!/usr/bin/env node

// Verify that the committed OpenAPI snapshots match their generators.
//
// Usage: node scripts/check-snapshots.cjs [models|api ...]
//
// With no arguments both snapshots are checked.

const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

const schemaRoot = path.resolve(__dirname, "..");

const snapshots = {
   models: {
      fileName: "kontext.models.openapi.json",
      generate(outFile) {
         execFileSync(
            "node",
            ["--import", "tsx", "scripts/export-schemas.mjs"],
            {
               cwd: schemaRoot,
               env: { ...process.env, KONTEXT_SCHEMA_OUT_FILE: outFile },
               stdio: "inherit"
            }
         );
      },
      hint: "Run `pnpm --filter @kontext-labs/schema refresh-schemas` and commit the result."
   },
   api: {
      fileName: "kontext.api.openapi.json",
      async generate(outFile) {
         // `fetch-api-openapi.cjs` resolves its output path at require time.
         process.env.KONTEXT_API_SCHEMA_OUT_FILE = outFile;
         const { fetchApiOpenAPISpec } = require("./fetch-api-openapi.cjs");
         await fetchApiOpenAPISpec();
      },
      hint: "Run `pnpm --filter @kontext-labs/schema refresh-api-schema` and commit the result."
   }
};

async function check(name) {
   const { fileName, generate, hint } = snapshots[name];
   const snapshotPath = path.join(schemaRoot, "src/schemas", fileName);
   const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "kontext-schema-"));
   const tempPath = path.join(tempDir, fileName);

   try {
      await generate(tempPath);

      const expected = fs.readFileSync(snapshotPath, "utf8");
      const actual = fs.readFileSync(tempPath, "utf8");

      if (expected !== actual) {
         throw new Error(`${fileName} is out of date. ${hint}`);
      }

      console.log(`ok ${name} schema snapshot is current`);
   } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
   }
}

async function main() {
   const targets = process.argv.slice(2);
   const selected = targets.length > 0 ? targets : Object.keys(snapshots);

   for (const name of selected) {
      if (!snapshots[name]) {
         throw new Error(
            `Unknown snapshot "${name}". Expected one of: ${Object.keys(snapshots).join(", ")}`
         );
      }
   }

   for (const name of selected) {
      await check(name);
   }
}

main().catch((error) => {
   console.error(error.message);
   process.exit(1);
});
