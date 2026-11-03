#!/usr/bin/env node
/**
 * Docs capture entry point.
 *
 *   node tools/docs-capture/run.mjs check [--strict]
 *   node tools/docs-capture/run.mjs capture [--only <page|story|flow>]
 *   node tools/docs-capture/run.mjs prune
 *   node tools/docs-capture/run.mjs report
 */
import fs from "node:fs";
import path from "node:path";

import { assetsDir, toolsDir } from "./lib/paths.mjs";
import { markdownFiles, stripCode, walkFiles } from "./lib/guide.mjs";
import { runChecks } from "./lib/checks.mjs";
import { writeReport } from "./lib/report.mjs";

const argv = process.argv.slice(2);
const command = argv[0] ?? "check";

const COMMANDS = new Set(["check", "capture", "record", "scaffold", "prune", "report"]);
const FLAGS_BY_COMMAND = {
   check: new Set(["--strict"]),
   capture: new Set(["--only"])
};

function usage() {
   console.log(
      [
         "Usage: node tools/docs-capture/run.mjs <command> [options]",
         "",
         "Commands:",
         "  check [--strict]           Verify coverage, links, images, and block hashes",
         "  capture [--only <target>]  Capture screenshots and regenerate guide blocks",
         "  record                     Record the chat transcript (needs a provider key)",
         "  scaffold                   Create missing page files",
         "  prune                      Delete images no page references",
         "  report                     Regenerate the capture report"
      ].join("\n")
   );
}

function fail(message) {
   console.error(message);
   process.exit(1);
}

if (command === "--help" || command === "-h") {
   usage();
   process.exit(0);
}
if (!COMMANDS.has(command)) {
   fail(`Unknown command "${command}". Run with --help to see the commands.`);
}

const flags = new Set();
let only = null;
const rest = argv.slice(1);
for (let index = 0; index < rest.length; index += 1) {
   const value = rest[index];
   if (value.startsWith("--only=")) {
      if (only !== null) fail("--only was provided more than once.");
      only = value.slice("--only=".length);
      if (!only) fail("--only needs a page, story, or flow name.");
      continue;
   }
   if (value === "--only") {
      const next = rest[index + 1];
      if (!next || next.startsWith("--")) fail("--only needs a page, story, or flow name.");
      if (only !== null) fail("--only was provided more than once.");
      only = next;
      index += 1;
      continue;
   }
   if (value === "--strict") {
      flags.add(value);
      continue;
   }
   fail(`Unknown option "${value}" for "${command}". Run with --help to see the options.`);
}

for (const flag of flags) {
   if (!FLAGS_BY_COMMAND[command]?.has(flag)) {
      fail(`Option "${flag}" is not valid for "${command}".`);
   }
}
if (only !== null && command !== "capture") {
   fail("--only is only valid for the capture command.");
}

function printCheck(result) {
   const { stats } = result;
   console.log(
      `Routes   ${stats.routes} total | ${stats.documented} documented | ${stats.excluded} excluded`
   );
   console.log(
      `Pages    ${stats.published} published | ${stats.drafts} draft | ${stats.stories} stories | ${stats.flows} flows`
   );
   console.log(
      `Images   ${stats.images} captured | ${stats.orphans} orphan${stats.orphans === 1 ? "" : "s"}`
   );

   for (const warning of result.warnings) {
      console.log(`warn   [${warning.rule}] ${warning.message}`);
   }
   for (const error of result.errors) {
      console.error(`error  [${error.rule}] ${error.message}`);
   }

   if (result.errors.length > 0) {
      console.error(
         `\n${result.errors.length} error${result.errors.length === 1 ? "" : "s"}, ` +
            `${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"}.`
      );
      return 1;
   }
   if (flags.has("--strict") && result.warnings.length > 0) {
      console.error(
         `\n${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"} treated as errors by --strict.`
      );
      return 1;
   }

   console.log(
      `\nDocs checks passed (${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"}).`
   );
   return 0;
}

function referencedImages() {
   const referenced = new Set();
   for (const file of markdownFiles(path.join(toolsDir, "..", "..", "docs"))) {
      const markdown = stripCode(fs.readFileSync(file, "utf8"));
      for (const match of markdown.matchAll(/!\[[^\]]*\]\(([^)\s]+)\)/g)) {
         if (/^(https?:|data:)/.test(match[1])) continue;
         referenced.add(path.resolve(path.dirname(file), match[1]));
      }
   }
   return referenced;
}

async function main() {
   if (command === "check") {
      const result = await runChecks({ strict: flags.has("--strict") });
      process.exit(printCheck(result));
   }

   if (command === "capture") {
      const { capture } = await import("./lib/capture.mjs");
      const result = await capture({ only });
      console.log(
         `Captured ${result.results.length} stories, wrote ${result.written.length} ` +
            `page${result.written.length === 1 ? "" : "s"}` +
            (result.created.length > 0 ? `, scaffolded ${result.created.length}.` : ".")
      );
      console.log(`Report: ${result.report}`);
      console.log(
         `Stamped ${result.meta.capturedWith} @ ${result.meta.commit} (${result.meta.capturedAt}).`
      );
      process.exit(0);
   }

   if (command === "record") {
      const { readDocsEnv } = await import("./lib/env.mjs");
      const env = readDocsEnv();
      if (!env.OLLAMA_CLOUD_API_KEY) {
         console.error(
            "OLLAMA_CLOUD_API_KEY is not set. Copy .env.docs.example to .env.docs.local and add the key."
         );
         process.exit(1);
      }

      const { startServer } = await import("./lib/seed.mjs");
      const { seedFixtures } = await import("./lib/fixtures.mjs");
      const { recordChat, writeTranscript } = await import("./lib/chat.mjs");

      const server = await startServer();
      try {
         await server.completeSetup();
         const token = await server.getToken();
         const { project, connection } = await seedFixtures({ server, token });
         const { messages } = await recordChat(server, {
            token,
            projectId: project.id,
            apiKey: env.OLLAMA_CLOUD_API_KEY,
            baseUrl: env.OLLAMA_CLOUD_BASE_URL || undefined,
            catalogConnectionId: connection.id
         });
         const file = writeTranscript({
            messages,
            apiKey: env.OLLAMA_CLOUD_API_KEY,
            homeDir: server.homeDir
         });
         console.log(`Recorded ${messages.length} messages -> ${file}`);
      } finally {
         await server.stop();
      }
      process.exit(0);
   }

   if (command === "scaffold") {
      const { scaffoldPages } = await import("./lib/capture.mjs");
      const created = scaffoldPages();
      console.log(
         `Scaffolded ${created.length} page${created.length === 1 ? "" : "s"}.`
      );
      process.exit(0);
   }

   if (command === "prune") {
      const referenced = referencedImages();
      const images = walkFiles(assetsDir, (file) => file.endsWith(".png"));
      const orphans = images.filter((file) => !referenced.has(file));
      for (const file of orphans) fs.rmSync(file);
      console.log(`Pruned ${orphans.length} orphan image${orphans.length === 1 ? "" : "s"}.`);
      process.exit(0);
   }

   if (command === "report") {
      console.log(`Report: ${writeReport()}`);
      process.exit(0);
   }

   console.error(`Unknown command "${command}". Use check, capture, prune, or report.`);
   process.exit(1);
}

main().catch((error) => {
   console.error(error.message);
   process.exit(1);
});
