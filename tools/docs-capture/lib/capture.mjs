import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { assetsDir, guideDir, repoRoot, toolsDir } from "./paths.mjs";
import { startServer } from "./seed.mjs";
import {
   clearHighlight,
   highlight,
   launchBrowser,
   navigate,
   openPage,
   sanitizeScreenshot,
   screenshot,
   screenshotClip,
   screenshotElement,
   scrollToTop,
   settle
} from "./browser.mjs";
import {
   loadStories,
   pageSkeleton,
   pages,
   readPage,
   renderSteps,
   replaceBlock
} from "./guide.mjs";
import { pageGroups } from "../pages.mjs";
import { writeReport } from "./report.mjs";
import { seedFixtures, stabilizeTimestamps } from "./fixtures.mjs";
import {
   ensureModelConnection,
   readTranscript,
   seedChatTranscript
} from "./chat.mjs";
import { FIXTURE_EPOCH } from "../fixtures.mjs";

async function runStage({
   browser,
   stories,
   baseUrl,
   homeDir,
   launchToken,
   onStoryComplete
}) {
   const results = [];
   for (const story of stories) {
      const { context, page } = await openPage(browser, { launchToken });
      let current = null;
      try {
         await navigate(page, baseUrl, story.goto ?? "/");
         if (story.collapseSidebar) {
            await page
               .getByRole("button", { name: "Collapse sidebar" })
               .click()
               .catch(() => {});
            await settle(page);
         }
         const steps = [];

         for (const step of story.steps) {
            current = step;
            if (step.goto) await navigate(page, baseUrl, step.goto);
            if (step.before) {
               await step.before(page);
               await settle(page);
            }

            // Client-side navigation keeps the previous scroll offset, which
            // shifts otherwise identical screenshots.
            await scrollToTop(page);

            if (step.target) {
               const locator = step.target(page).first();
               await locator.waitFor({ state: "visible" });
               await highlight(page, locator);
            }

            if (step.shot !== false) {
               await sanitizeScreenshot(page, { homeDir });
               // Text normalization can reflow a virtualized list and move its
               // scroll position, so let a step reset it after sanitizing.
               if (step.afterSanitize) await step.afterSanitize(page);
               const imagePath = path.join(
                  assetsDir,
                  story.page,
                  `${step.imageId ?? step.id}.png`
               );
               const beforeCapture = () => sanitizeScreenshot(page, { homeDir });
               if (step.screenshotClip) {
                  await screenshotClip(page, await step.screenshotClip(page), imagePath, {
                     beforeCapture
                  });
               } else if (step.screenshotTarget) {
                  const element = step.screenshotTarget(page).first();
                  await element.waitFor({ state: "visible" });
                  await screenshotElement(page, element, imagePath, { beforeCapture });
               } else {
                  await screenshot(page, imagePath, { beforeCapture });
               }
            }

            await clearHighlight(page);
            steps.push({ id: step.id, caption: step.caption, shot: step.shot !== false });

            if (step.after) {
               await step.after(page);
               await settle(page);
            }
         }

         results.push({ story, steps });
         if (onStoryComplete) await onStoryComplete(story);
      } catch (error) {
         const failures = path.join(toolsDir, "report", "failures");
         fs.mkdirSync(failures, { recursive: true });
         const failureFile = path.join(
            failures,
            `${story.id}${current ? `-${current.id}` : ""}.png`
         );
         await screenshot(page, failureFile).catch(() => {});
         throw new Error(
            `Story ${story.id} failed${current ? ` at step ${current.id}` : ""}: ${error.message}\n` +
               `Failure screenshot: ${failureFile}`
         );
      } finally {
         await context.close();
      }
   }
   return results;
}

function ensurePages() {
   const created = [];
   for (const page of pages) {
      const file = path.join(guideDir, `${page.slug}.md`);
      if (!fs.existsSync(file)) {
         fs.mkdirSync(guideDir, { recursive: true });
         fs.writeFileSync(file, pageSkeleton(page));
         created.push(page.slug);
      }
   }
   return created;
}

function writeMarkdown(results) {
   const written = [];
   for (const page of pages) {
      const pageResults = results.filter((result) => result.story.page === page.slug);
      if (pageResults.length === 0) continue;

      const slots = new Map();
      for (const result of pageResults) {
         const slot = result.story.slot ?? 1;
         if (!slots.has(slot)) slots.set(slot, []);
         slots.get(slot).push(...result.steps);
      }

      let markdown = readPage(page.slug) ?? pageSkeleton(page);
      for (const [slot, steps] of slots) {
         const story = pageResults.find(
            (result) => (result.story.slot ?? 1) === slot
         ).story;
         markdown = replaceBlock(markdown, page.slug, slot, renderSteps(story, steps));
      }
      fs.writeFileSync(path.join(guideDir, `${page.slug}.md`), markdown);
      written.push(page.slug);
   }
   return written;
}

function writeGuideIndex() {
   const published = pages
      .filter((page) => page.status === "published")
      .sort((a, b) => a.order - b.order);

   const lines = [
      "# Kontext Labs user guide",
      "",
      "Kontext Labs is a local-first AI data workspace. Connect your files and",
      "databases, bring your own model, and ask questions in plain language. A team of",
      "agents returns SQL results, charts, and reproducible notebooks — all on your",
      "machine.",
      "",
      "This guide is task-oriented: each page covers one workflow, with the",
      "screens and controls you need. Start with installation if you are new, or",
      "jump to the page for the task you are doing.",
      ""
   ];

   for (const group of pageGroups) {
      const groupPages = published.filter((page) => page.group === group.id);
      if (groupPages.length === 0) {
         continue;
      }
      lines.push(`## ${group.label}`, "");
      for (const page of groupPages) {
         lines.push(`- [${page.title}](${page.slug}.md) — ${page.summary}`);
      }
      lines.push("");
   }

   fs.mkdirSync(guideDir, { recursive: true });
   fs.writeFileSync(path.join(guideDir, "README.md"), lines.join("\n"));
}

function writeMeta() {
   const pkg = JSON.parse(fs.readFileSync(path.join(repoRoot, "package.json"), "utf8"));
   let commit = "unknown";
   try {
      commit = execFileSync("git", ["rev-parse", "--short", "HEAD"], {
         cwd: repoRoot,
         encoding: "utf8"
      }).trim();
   } catch {
      // Capturing outside a git checkout is allowed.
   }

   const meta = {
      capturedWith: pkg.version,
      capturedAt: new Date().toISOString(),
      commit
   };
   fs.mkdirSync(guideDir, { recursive: true });
   fs.writeFileSync(
      path.join(guideDir, "_meta.json"),
      `${JSON.stringify(meta, null, 3)}\n`
   );
   return meta;
}

export async function capture({ only = null } = {}) {
   const stories = await loadStories();
   let selected = only
      ? stories.filter(
           (story) => story.page === only || story.id === only || story.id === `flow:${only}`
         )
      : stories;

   if (selected.length === 0) {
      throw new Error(`No stories match "${only}".`);
   }

   // A targeted capture still needs the stories that produce state another
   // story reads. Pull declared prerequisites in and restore capture order.
   const byId = new Map(stories.map((story) => [story.id, story]));
   const wanted = new Set(selected.map((story) => story.id));
   const queue = [...selected];
   while (queue.length > 0) {
      const story = queue.shift();
      for (const dependency of story.requires ?? []) {
         if (wanted.has(dependency)) continue;
         const required = byId.get(dependency);
         if (!required) {
            throw new Error(`${story.id} requires unknown story "${dependency}".`);
         }
         wanted.add(dependency);
         queue.push(required);
      }
   }
   selected = stories.filter((story) => wanted.has(story.id));

   // Notebook and job pages capture real executions, so the local job worker
   // must run alongside the API. Without it, queued runs never leave Queued.
   const server = await startServer();
   let browser;
   const results = [];

   try {
      browser = await launchBrowser();

      const unconfigured = selected.filter((story) => story.stage === "unconfigured");
      results.push(
         ...(await runStage({
            browser,
            stories: unconfigured,
            baseUrl: server.baseUrl,
            homeDir: server.homeDir,
            launchToken: server.launchToken
         }))
      );

      if (!(await server.setupStatus())) {
         await server.completeSetup();
      }

      const token = await server.getToken();
      if (!token) {
         throw new Error(
            "Local console did not issue a token after setup; cannot seed fixtures."
         );
      }
      const { project } = await seedFixtures({ server, token });
      const connection = await ensureModelConnection(server, {
         token,
         apiKey: "docs-fixture-key"
      });
      if (readTranscript()) {
         seedChatTranscript(server, {
            projectId: project.id,
            modelSelectionId: connection.id,
            epoch: FIXTURE_EPOCH
         });
      }

      if (selected.some((story) => story.needsWorker)) {
         await server.startWorker();
         await server.waitForIdleJobs();
         // The worker completed the runs that were queued during seeding; stamp
         // their times again so the list and drawer are stable.
         stabilizeTimestamps(server);
      }

      const configured = selected.filter((story) => story.stage === "configured");
      results.push(
         ...(await runStage({
            browser,
            stories: configured,
            baseUrl: server.baseUrl,
            homeDir: server.homeDir,
            launchToken: server.launchToken,
            onStoryComplete: async (story) => {
               // Runs created during a capture carry the real wall clock, which
               // is later than the frozen page clock. Restamp them so later
               // stories render them like the seeded runs.
               if (story.stabilizeAfter) stabilizeTimestamps(server);
            }
         }))
      );
   } finally {
      await browser?.close();
      await server.stopWorker();
      await server.stop();
   }

   const created = ensurePages();
   const written = writeMarkdown(results);
   writeGuideIndex();
   const meta = writeMeta();
   const report = writeReport();

   return { results, created, written, meta, report };
}

export function scaffoldPages() {
   const created = ensurePages();
   writeGuideIndex();
   return created;
}
