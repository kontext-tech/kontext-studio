/**
 * Re-capture the user guide and fail if the committed docs drift.
 *
 * This is the reproducibility check that CI cannot run on every pull request:
 * it needs Chromium, uv, and a real app build. Run it locally before publishing
 * a docs change, or on a schedule.
 *
 * Screenshot bytes depend on the host's font rasterization, so the scheduled
 * Linux run cannot compare them against images captured on a maintainer's
 * machine. Set `DOCS_VERIFY_SCREENSHOTS=warn` there: modified PNGs are reported
 * and uploaded for review, while changed markdown, new files, and deleted files
 * still fail. Local runs stay strict.
 */
import { execFileSync } from "node:child_process";

import { repoRoot } from "./lib/paths.mjs";

const screenshotMode = process.env.DOCS_VERIFY_SCREENSHOTS ?? "fail";
if (!["fail", "warn"].includes(screenshotMode)) {
   console.error(
      `DOCS_VERIFY_SCREENSHOTS must be "fail" or "warn", not "${screenshotMode}".`
   );
   process.exit(1);
}

function run(command, args) {
   execFileSync(command, args, { cwd: repoRoot, stdio: "inherit" });
}

run(process.execPath, ["tools/docs-capture/run.mjs", "capture"]);
run(process.execPath, ["tools/docs-capture/run.mjs", "check", "--strict"]);

// `git diff` misses new files. Ask `git status` instead, and ignore the capture
// timestamp, which changes on every run by design.
const status = execFileSync("git", ["status", "--porcelain", "--", "docs/"], {
   cwd: repoRoot,
   encoding: "utf8"
});
const changed = status
   .split("\n")
   .filter(Boolean)
   .filter((line) => !line.endsWith("docs/user-guide/_meta.json"));

function isModifiedScreenshot(line) {
   return line.startsWith(" M") && line.trimEnd().endsWith(".png");
}

const screenshots = changed.filter(isModifiedScreenshot);
const blocking = changed.filter((line) => !isModifiedScreenshot(line));

if (blocking.length > 0) {
   console.error(
      "\nCaptured docs differ from the committed output:\n" +
         blocking.map((line) => `  ${line}`).join("\n") +
         "\n\nCommit the regenerated files, or fix whatever made the capture nondeterministic."
   );
   process.exit(1);
}

if (screenshots.length > 0 && screenshotMode === "fail") {
   console.error(
      "\nCaptured screenshots differ from the committed output:\n" +
         screenshots.map((line) => `  ${line}`).join("\n") +
         "\n\nReview them via tools/docs-capture/report/index.html, then commit the regenerated images."
   );
   process.exit(1);
}

if (screenshots.length > 0) {
   console.warn(
      `\n${screenshots.length} screenshot${screenshots.length === 1 ? "" : "s"} differ from the committed ` +
         "output. Host font rendering differs, so review them via " +
         "tools/docs-capture/report/index.html rather than treating this as a failure.\n"
   );
}

console.log("[docs-capture] verified: re-capturing reproduces the committed guide.");
