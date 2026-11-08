/**
 * Record demo clips (GIF and MP4) for stories with `kind: "media"`.
 *
 * Screenshots are captured one frame at a time and can be verified
 * byte-for-byte. Clips are recorded continuously and cannot be, so media
 * stories get their own browser context (animations on, real clock, 1x pixels),
 * their own output destinations, and metadata checks instead of hashes.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { launchBrowser, settle } from "./browser.mjs";
import { prepareConfiguredState } from "./capture.mjs";
import { loadStories, readPage, renderSteps, replaceBlock } from "./guide.mjs";
import { assetsDir, guideDir, mediaManifestFile, repoRoot } from "./paths.mjs";
import { startServer } from "./seed.mjs";
import { stabilizeTimestamps } from "./fixtures.mjs";

const DEFAULT_VIEWPORT = { width: 1280, height: 800 };
const DEFAULT_WIDTH = 1200;
const DEFAULT_FPS = 15;
const DEFAULT_PAUSE_MS = 1200;
const DEFAULT_HOLD_MS = 800;

export const MEDIA_GIF_BUDGET_BYTES = 8 * 1024 * 1024;
export const MEDIA_MAX_SECONDS = 20;

export function mediaSlug(story) {
   return story.id.replace(/^media:/, "");
}

function relativeRepo(file) {
   return path.relative(repoRoot, file).split(path.sep).join("/");
}

function mediaPaths(story) {
   const slug = mediaSlug(story);
   const base =
      (story.destination ?? "docs") === "site"
         ? path.join(repoRoot, "docs-site", "public", "media")
         : path.join(assetsDir, story.page);
   return {
      base,
      gif: path.join(base, `${slug}.gif`),
      mp4: path.join(base, `${slug}.mp4`),
      poster: path.join(base, `${slug}-poster.png`)
   };
}

function writePoster(mp4, output, at) {
   execFileSync(
      "ffmpeg",
      ["-y", "-i", mp4, "-ss", String(at), "-frames:v", "1", output],
      { stdio: ["ignore", "ignore", "pipe"] }
   );
}

function hasBinary(command, args) {
   try {
      execFileSync(command, args, { stdio: "ignore" });
      return true;
   } catch {
      return false;
   }
}

function requireFfmpeg() {
   if (!hasBinary("ffmpeg", ["-version"]) || !hasBinary("ffprobe", ["-version"])) {
      throw new Error(
         "Media capture needs ffmpeg and ffprobe. Install them with `brew install ffmpeg` " +
            "(macOS), `winget install ffmpeg` (Windows), or your package manager."
      );
   }
}

function encodeMp4(webm, output, { fps, width, trimStart = 0 }) {
   const args = ["-y", "-i", webm];
   // Output seeking decodes and discards, so the cut lands on the requested
   // frame instead of the preceding keyframe.
   if (trimStart > 0) args.push("-ss", String(trimStart));
   args.push(
      "-vf",
      `fps=${fps},scale=${width}:-2:flags=lanczos`,
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-crf",
      "23",
      "-movflags",
      "+faststart",
      "-an",
      output
   );
   execFileSync("ffmpeg", args, { stdio: ["ignore", "ignore", "pipe"] });
}

/**
 * Encode the GIF from the CFR MP4, not the raw WebM.
 *
 * ffmpeg's palette pass is the portable fallback and needs no extra tool;
 * gifski is only a quality upgrade for gradients and per-frame timing.
 */
function encodeGif(mp4, output, { fps, width }) {
   if (hasBinary("gifski", ["--version"])) {
      const framesDir = fs.mkdtempSync(path.join(os.tmpdir(), "kontext-media-frames-"));
      try {
         execFileSync(
            "ffmpeg",
            [
               "-y",
               "-i",
               mp4,
               "-vf",
               `scale=${width}:-2:flags=lanczos`,
               path.join(framesDir, "%05d.png")
            ],
            { stdio: ["ignore", "ignore", "pipe"] }
         );
         const frames = fs
            .readdirSync(framesDir)
            .filter((file) => file.endsWith(".png"))
            .sort()
            .map((file) => path.join(framesDir, file));
         execFileSync(
            "gifski",
            ["--fps", String(fps), "--width", String(width), "-o", output, ...frames],
            { stdio: ["ignore", "ignore", "pipe"] }
         );
      } finally {
         fs.rmSync(framesDir, { recursive: true, force: true });
      }
      return "gifski";
   }

   const filter = [
      `scale=${width}:-2:flags=lanczos,split[a][b]`,
      "[a]palettegen=stats_mode=diff[p]",
      "[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"
   ].join(";");
   execFileSync(
      "ffmpeg",
      ["-y", "-i", mp4, "-vf", filter, "-loop", "0", output],
      { stdio: ["ignore", "ignore", "pipe"] }
   );
   return "ffmpeg";
}

function probeVideo(file) {
   const output = execFileSync(
      "ffprobe",
      [
         "-v",
         "error",
         "-select_streams",
         "v:0",
         "-show_entries",
         "stream=width,height",
         "-show_entries",
         "format=duration",
         "-of",
         "json",
         file
      ],
      { encoding: "utf8" }
   );
   const parsed = JSON.parse(output);
   return {
      width: parsed.streams?.[0]?.width ?? null,
      height: parsed.streams?.[0]?.height ?? null,
      durationSeconds: Number(parsed.format?.duration ?? 0)
   };
}

/**
 * Draw a pointer in the page.
 *
 * Playwright does not render a cursor, which makes a clip hard to follow.
 * Stories move this dot before clicking with the helpers passed to each step.
 */
async function installPointer(page) {
   await page.addInitScript(() => {
      window.__docsMediaPointer = (x, y) => {
         let dot = document.getElementById("docs-media-pointer");
         if (!dot) {
            dot = document.createElement("div");
            dot.id = "docs-media-pointer";
            Object.assign(dot.style, {
               position: "fixed",
               left: "0",
               top: "0",
               width: "18px",
               height: "18px",
               marginLeft: "-9px",
               marginTop: "-9px",
               borderRadius: "999px",
               border: "2px solid rgba(22, 119, 255, 0.9)",
               background: "rgba(22, 119, 255, 0.16)",
               boxShadow: "0 0 0 1px rgba(255, 255, 255, 0.8)",
               pointerEvents: "none",
               zIndex: "2147483647",
               transition: "transform 160ms ease-out",
               opacity: "0"
            });
            document.body.appendChild(dot);
         }
         dot.style.transform = `translate(${x}px, ${y}px)`;
         dot.style.opacity = "1";
      };
   });
}

function makeHelpers(page) {
   const moveTo = async (locator) => {
      await locator.scrollIntoViewIfNeeded().catch(() => {});
      const box = await locator.boundingBox().catch(() => null);
      if (!box) return;
      await page.evaluate(
         ({ x, y }) => window.__docsMediaPointer?.(x, y),
         { x: box.x + box.width / 2, y: box.y + box.height / 2 }
      );
      await page.waitForTimeout(220);
   };
   const click = async (locator) => {
      await moveTo(locator);
      await locator.click();
   };
   return { moveTo, click, pause: (ms) => page.waitForTimeout(ms) };
}

async function api(server, token, pathname, init = {}) {
   const response = await fetch(`${server.apiUrl}${pathname}`, {
      ...init,
      headers: {
         Authorization: `Bearer ${token}`,
         "content-type": "application/json",
         ...init.headers
      }
   });
   const text = await response.text();
   let body = text;
   try {
      body = text ? JSON.parse(text) : null;
   } catch {
      // Keep non-JSON error payloads for the thrown message.
   }
   if (!response.ok) {
      throw new Error(
         `Query session request ${pathname} failed with ${response.status}: ${text.slice(0, 400)}`
      );
   }
   return body?.data ?? body;
}

/**
 * Seed an active query session bound to the fixture's catalog connection.
 *
 * A notebook SQL block executes through the project's session; a session
 * created from the UI defaults to the internal lakehouse, where the fixture's
 * tables do not exist. The worker occasionally starts before it can see the
 * seeded connection, so a failed initialization is retried once with a fresh
 * session.
 */
async function ensureQuerySession(server, { project, catalogConnection, token }) {
   let lastFailure = null;
   for (let attempt = 0; attempt < 2; attempt += 1) {
      const created = await api(server, token, "/session", {
         method: "POST",
         body: JSON.stringify({
            projectId: project.id,
            sessionName: "Music store analysis",
            catalogConnectionId: catalogConnection.id
         })
      });
      const sessionId = created?.id;
      if (!sessionId) {
         throw new Error("Query session creation returned no id.");
      }

      const initialized = await api(server, token, "/session/init", {
         method: "POST",
         body: JSON.stringify({
            projectId: project.id,
            sessionId,
            catalogConnectionId: catalogConnection.id
         })
      });
      if (initialized?.success !== false) {
         return created;
      }
      lastFailure = initialized;
      await new Promise((resolve) => setTimeout(resolve, 1_500));
   }

   throw new Error(
      `Query session failed to initialize: ${JSON.stringify(lastFailure)}`
   );
}

async function recordStory({ browser, server, story, launchToken }) {
   requireFfmpeg();

   const viewport = story.viewport ?? DEFAULT_VIEWPORT;
   const fps = story.fps ?? DEFAULT_FPS;
   const width = story.width ?? DEFAULT_WIDTH;
   const formats = new Set(story.formats ?? ["gif", "mp4"]);
   const colorScheme = story.colorScheme ?? "light";
   let trimStart = story.trimStart ?? 0;
   const videoDir = fs.mkdtempSync(path.join(os.tmpdir(), "kontext-media-"));

   const context = await browser.newContext({
      viewport,
      deviceScaleFactor: 1,
      colorScheme,
      locale: "en-US",
      timezoneId: "UTC",
      // Unlike screenshots, a clip needs motion and a live clock.
      reducedMotion: "no-preference",
      recordVideo: { dir: videoDir, size: viewport }
   });
   if (launchToken) {
      await context.addInitScript((token) => {
         try {
            window.sessionStorage.setItem("kontext.launch.token", token);
         } catch {
            // Storage can be unavailable; the page will show the login state.
         }
      }, launchToken);
   }

   const page = await context.newPage();
   const recordingStart = Date.now();
   page.setDefaultTimeout(120_000);
   await installPointer(page);
   const video = page.video();

   try {
      await page.goto(new URL(story.goto, server.baseUrl).href, {
         waitUntil: "domcontentloaded"
      });
      await settle(page);

      if (story.collapseSidebar) {
         await page
            .getByRole("button", { name: "Collapse sidebar" })
            .click()
            .catch(() => {});
         await page.waitForTimeout(400);
      }

      const helpers = makeHelpers(page);
      if (story.ready) await story.ready(page, helpers);
      if (story.trimToReady) {
         // The router briefly renders the default screen before the target
         // route. Cut the recording to the point the story state is ready,
         // keeping a short lead-in so the first action is still visible.
         trimStart = Math.max(
            trimStart,
            (Date.now() - recordingStart) / 1000 - 0.3
         );
      }
      if (story.before) await story.before(page, helpers);
      for (const step of story.steps) {
         if (step.before) await step.before(page, helpers);
         await page.waitForTimeout(step.pause ?? DEFAULT_PAUSE_MS);
         if (step.after) await step.after(page, helpers);
      }
      await page.waitForTimeout(story.hold ?? DEFAULT_HOLD_MS);
   } finally {
      await context.close();
   }

   const webm = await video.path();
   if (!webm) {
      throw new Error(`Playwright produced no video for ${story.id}.`);
   }

   const outputs = mediaPaths(story);
   fs.mkdirSync(outputs.base, { recursive: true });
   encodeMp4(webm, outputs.mp4, { fps, width, trimStart });
   const encoder = formats.has("gif") ? encodeGif(outputs.mp4, outputs.gif, { fps, width }) : null;
   let poster = null;
   if ((story.destination ?? "docs") === "site" && story.poster !== false) {
      poster = outputs.poster;
      writePoster(outputs.mp4, poster, story.posterAt ?? 1);
   }
   const info = probeVideo(outputs.mp4);
   const record = {
      id: story.id,
      page: story.page,
      destination: story.destination ?? "docs",
      formats: [...formats].sort(),
      gif: formats.has("gif") ? relativeRepo(outputs.gif) : null,
      mp4: relativeRepo(outputs.mp4),
      poster: poster ? relativeRepo(poster) : null,
      width: info.width,
      height: info.height,
      fps,
      durationSeconds: Number(info.durationSeconds.toFixed(2)),
      gifBytes: formats.has("gif") ? fs.statSync(outputs.gif).size : 0,
      mp4Bytes: fs.statSync(outputs.mp4).size,
      encoder
   };

   if (process.env.DOCS_KEEP_MEDIA === "1") {
      console.log(`Kept recording: ${webm}`);
   } else {
      fs.rmSync(videoDir, { recursive: true, force: true });
   }
   return record;
}

/**
 * Media stories with a slot also write a guide block, so the clip sits in the
 * page next to the screenshots and is covered by the block-hash check.
 */
function writeMediaMarkdown(stories) {
   const written = new Set();
   for (const story of stories) {
      if ((story.destination ?? "docs") !== "docs") continue;
      if (!story.slot) continue;

      const markdown = readPage(story.page);
      if (!markdown) {
         throw new Error(
            `Media story ${story.id} targets page ${story.page}, which has no guide markdown.`
         );
      }

      const content = renderSteps(
         { page: story.page },
         [{ id: mediaSlug(story), caption: story.caption }],
         { extension: "gif" }
      );
      fs.writeFileSync(
         path.join(guideDir, `${story.page}.md`),
         replaceBlock(markdown, story.page, story.slot, content)
      );
      written.add(story.page);
   }
   return [...written];
}

function writeMediaManifest(records) {
   // A targeted run rewrites only its own clips; keep the others so a partial
   // capture does not shrink the check's coverage.
   let existing = [];
   if (fs.existsSync(mediaManifestFile)) {
      try {
         existing = JSON.parse(fs.readFileSync(mediaManifestFile, "utf8")).items ?? [];
      } catch {
         existing = [];
      }
   }
   const byId = new Map(existing.map((item) => [item.id, item]));
   for (const record of records) byId.set(record.id, record);

   const payload = {
      generatedAt: new Date().toISOString(),
      items: [...byId.values()].sort((left, right) =>
         left.id.localeCompare(right.id)
      )
   };
   fs.mkdirSync(path.dirname(mediaManifestFile), { recursive: true });
   fs.writeFileSync(
      mediaManifestFile,
      `${JSON.stringify(payload, null, 3)}\n`
   );
   return mediaManifestFile;
}

export async function captureMedia({ only = null } = {}) {
   const stories = (await loadStories()).filter(
      (story) => (story.kind ?? "screen") === "media"
   );
   if (stories.length === 0) {
      throw new Error("No media stories found in tools/docs-capture/stories/media.");
   }

   const selected = only
      ? stories.filter(
           (story) =>
              story.id === only ||
              mediaSlug(story) === only ||
              story.page === only
        )
      : stories;
   if (selected.length === 0) {
      throw new Error(`No media story matches "${only}".`);
   }

   const server = await startServer();
   let browser;
   const records = [];

   try {
      browser = await launchBrowser();
      const prepared = await prepareConfiguredState(server, selected);
      if (selected.some((story) => story.needsQuerySession)) {
         await ensureQuerySession(server, prepared);
      }

      for (const story of selected) {
         console.log(`Recording ${story.id}...`);
         records.push(
            await recordStory({
               browser,
               server,
               story,
               launchToken: server.launchToken
            })
         );
         if (story.stabilizeAfter) stabilizeTimestamps(server);
      }
   } finally {
      await browser?.close();
      await server.stopWorker();
      await server.stop();
   }

   const written = writeMediaMarkdown(selected);
   const manifest = writeMediaManifest(records);
   return { records, written, manifest };
}
