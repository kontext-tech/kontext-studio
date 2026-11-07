import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { manifest } from "../manifest.mjs";
import { pages } from "../pages.mjs";
import { guideDir, repoRoot, toolsDir } from "./paths.mjs";

export const MARKER = /<!-- docs:capture ([\w-]+)(?:#(\d+))?(?: hash=([0-9a-f]+))? -->\n([\s\S]*?)<!-- \/docs:capture -->/g;

export function hashContent(content) {
   return crypto.createHash("sha256").update(content).digest("hex").slice(0, 12);
}

/**
 * Remove fenced code blocks and inline code spans so documentation rules do
 * not fire on examples. Architecture docs legitimately show image syntax inside
 * code; only real embeds should fail the audience checks.
 */
export function stripFencedBlocks(markdown) {
   const lines = markdown.split("\n");
   const out = [];
   let fenced = false;
   for (const line of lines) {
      if (/^\s*```/.test(line)) {
         fenced = !fenced;
         out.push("");
         continue;
      }
      out.push(fenced ? "" : line);
   }
   return out.join("\n");
}

export function stripCode(markdown) {
   return stripFencedBlocks(markdown).replace(/`[^`\n]*`/g, "");
}

export function walkFiles(dir, predicate) {
   if (!fs.existsSync(dir)) return [];
   const out = [];
   for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
         out.push(...walkFiles(full, predicate));
      } else if (predicate(full)) {
         out.push(full);
      }
   }
   return out;
}

export function markdownFiles(dir) {
   return walkFiles(dir, (file) => file.endsWith(".md"));
}

export function readPage(slug) {
   const file = path.join(guideDir, `${slug}.md`);
   if (!fs.existsSync(file)) return null;
   return fs.readFileSync(file, "utf8");
}

/**
 * Turn a caption into image alt text.
 *
 * Strip the markdown markers but keep the words inside inline code: captions
 * name identifiers such as `revenue_by_country` and `kontext.load_data`, and
 * dropping the underscores makes the alt text describe a different symbol.
 */
export function captionText(caption) {
   return caption
      .replace(/`([^`]*)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
}

export function renderSteps(story, steps, { extension = "png" } = {}) {
   const lines = [];
   let index = 1;
   for (const step of steps) {
      lines.push(`${index}. ${step.caption}`);
      if (step.shot !== false) {
         const image = imagePath(story.page, step.imageId ?? step.id, extension);
         const alt = captionText(step.caption);
         lines.push(`   ![${alt}](${image})`);
      }
      index += 1;
   }
   return `${lines.join("\n")}\n`;
}

export function imagePath(pageSlug, stepId, extension = "png") {
   return `assets/${pageSlug}/${stepId}.${extension}`;
}

export function replaceBlock(markdown, slug, slot, content) {
   const hash = hashContent(content);
   const suffix = slot > 1 ? `#${slot}` : "";
   const open = `<!-- docs:capture ${slug}${suffix} hash=${hash} -->`;
   const close = "<!-- /docs:capture -->";
   const block = `${open}\n${content}${close}`;
   MARKER.lastIndex = 0;
   const matches = [...markdown.matchAll(MARKER)];
   const existing = matches.find(
      (match) => match[1] === slug && Number(match[2] ?? 1) === slot
   );
   if (!existing) {
      return `${markdown.trimEnd()}\n\n${block}\n`;
   }
   return (
      markdown.slice(0, existing.index) +
      block +
      markdown.slice(existing.index + existing[0].length)
   );
}

export function readBlocks(markdown, slug) {
   MARKER.lastIndex = 0;
   return [...markdown.matchAll(MARKER)]
      .filter((match) => match[1] === slug)
      .map((match) => ({
         slot: Number(match[2] ?? 1),
         content: match[4],
         hash: match[3]
      }));
}

export function pageSkeleton(page) {
   return [
      `# ${page.title}`,
      "",
      `<!-- Write the introduction for this page. ${page.summary} -->`,
      "",
      `<!-- docs:capture ${page.slug} -->`,
      "<!-- /docs:capture -->",
      ""
   ].join("\n");
}

export async function loadStories() {
   const files = [
      ...walkFiles(path.join(toolsDir, "stories"), (file) => file.endsWith(".mjs")),
      ...walkFiles(path.join(toolsDir, "stories"), (file) => file.endsWith(".js"))
   ].sort();

   const stories = [];
   for (const file of files) {
      const module = await import(pathToFileURL(file).href);
      const story = module.default;
      if (!story) {
         throw new Error(`${path.relative(repoRoot, file)} has no default export.`);
      }
      story.source = path.relative(repoRoot, file);
      stories.push(story);
   }
   return stories.sort(
      (left, right) =>
         (left.order ?? 100) - (right.order ?? 100) ||
         left.source.localeCompare(right.source)
   );
}

export function validateStories(stories) {
   const problems = [];
   const ids = new Set();
   const pageMap = new Map(pages.map((page) => [page.slug, page]));

   for (const story of stories) {
      if (!story.id) problems.push(`${story.source}: missing id.`);
      if (ids.has(story.id)) problems.push(`${story.source}: duplicate id ${story.id}.`);
      ids.add(story.id);

      if (!pageMap.has(story.page)) {
         problems.push(`${story.source}: page ${story.page} is not in pages.mjs.`);
      }
      if (!["unconfigured", "configured"].includes(story.stage)) {
         problems.push(`${story.source}: stage must be unconfigured or configured.`);
      }

      const kind = story.kind ?? "screen";
      if (!["screen", "media"].includes(kind)) {
         problems.push(`${story.source}: kind must be screen or media.`);
      }
      if (kind === "media") {
         // Media stories record continuously after setup, so they cannot drive
         // the unconfigured screens that run before fixtures are seeded.
         if (story.stage !== "configured") {
            problems.push(`${story.source}: media stories must use stage configured.`);
         }
         if (!["docs", "site"].includes(story.destination ?? "docs")) {
            problems.push(`${story.source}: destination must be docs or site.`);
         }
         if (!story.goto) {
            problems.push(`${story.source}: media story ${story.id} needs a goto route.`);
         }
         if (story.slot && !story.caption) {
            problems.push(
               `${story.source}: media story ${story.id} needs a caption to write a guide block.`
            );
         }
         if (
            story.formats &&
            (!Array.isArray(story.formats) ||
               story.formats.some((format) => !["gif", "mp4"].includes(format)))
         ) {
            problems.push(`${story.source}: formats may only contain gif and mp4.`);
         }
      }

      const stepIds = new Set();
      for (const step of story.steps ?? []) {
         if (!step.id) problems.push(`${story.source}: a step is missing id.`);
         if (stepIds.has(step.id)) {
            problems.push(`${story.source}: duplicate step id ${step.id}.`);
         }
         stepIds.add(step.id);
         // Media steps are timed actions inside one clip; the story-level
         // caption describes the whole recording.
         if (kind !== "media" && !step.caption) {
            problems.push(`${story.source}: step ${step.id} is missing a caption.`);
         }
      }
      if (!story.steps || story.steps.length === 0) {
         problems.push(`${story.source}: story has no steps.`);
      }
   }

   return problems;
}

export { manifest, pages };
