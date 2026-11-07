import fs from "node:fs";
import path from "node:path";

import { EXCLUSION_REASONS, manifest } from "../manifest.mjs";
import { pages } from "../pages.mjs";
import {
   assetsDir,
   docsDir,
   guideDir,
   mediaManifestFile,
   repoRoot
} from "./paths.mjs";
import { buildInventory, serializeInventory } from "./inventory.mjs";
import {
   MARKER,
   hashContent,
   loadStories,
   markdownFiles,
   stripCode,
   stripFencedBlocks,
   validateStories,
   walkFiles
} from "./guide.mjs";

const FORBIDDEN_IN_GUIDE = [
   { label: "pnpm", pattern: /\bpnpm\s/ },
   { label: "uv sync", pattern: /\buv sync\b/ },
   { label: "py/", pattern: /(^|[^A-Za-z0-9_-])py\// },
   { label: "ts/", pattern: /(^|[^A-Za-z0-9_-])ts\// },
   { label: "@kontext-* scope", pattern: /@kontext-(labs|tech)\// },
   { label: "pytest", pattern: /\bpytest\b/ },
   { label: "AGENTS.md", pattern: /AGENTS\.md/ }
];

const CREDENTIAL_PATTERNS = [
   /sk-[A-Za-z0-9_-]{16,}/,
   /AKIA[0-9A-Z]{16}/,
   /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
   /Bearer\s+[A-Za-z0-9._-]{20,}/
];

const IMAGE_LINK = /!\[[^\]]*\]\(([^)\s]+)\)/g;

// Clips are recorded continuously, so they cannot be hashed like screenshots.
// These bounds keep a page's GIF from turning into a multi-megabyte download.
const MAX_MEDIA_BYTES = 8 * 1024 * 1024;
const MAX_MEDIA_SECONDS = 20;

function relative(file) {
   return path.relative(repoRoot, file);
}

function pageImages(slug) {
   const dir = path.join(assetsDir, slug);
   if (!fs.existsSync(dir)) return [];
   return walkFiles(dir, (file) => file.endsWith(".png"));
}

function textFiles(dir, extensions) {
   return walkFiles(dir, (file) => extensions.some((ext) => file.endsWith(ext)));
}

export async function runChecks({ strict = false } = {}) {
   const errors = [];
   const warnings = [];
   const add = (level, rule, message) => {
      (level === "error" ? errors : warnings).push({ rule, message });
   };

   const inventory = buildInventory();
   const routeNames = new Set(inventory.routes.map((route) => route.name));
   const routeByName = new Map(inventory.routes.map((route) => [route.name, route]));
   const pageBySlug = new Map(pages.map((page) => [page.slug, page]));
   const stories = await loadStories();

   // 1. Manifest and route table agree in both directions.
   for (const route of inventory.routes) {
      if (!manifest[route.name]) {
         add("error", "manifest", `Route ${route.name} is unclaimed. Document or exclude it.`);
      }
   }
   for (const name of Object.keys(manifest)) {
      if (!routeNames.has(name)) {
         add("error", "manifest", `Manifest entry ${name} has no matching route.`);
      }
   }

   // 2. Exclusions carry a known reason.
   for (const [name, entry] of Object.entries(manifest)) {
      if (entry.kind === "excluded" && !EXCLUSION_REASONS.includes(entry.reason)) {
         add("error", "manifest", `${name} has unknown exclusion reason ${entry.reason}.`);
      }
   }

   // 3. Documented routes point at a declared page.
   for (const [name, entry] of Object.entries(manifest)) {
      if (entry.kind !== "documented") continue;
      if (!pageBySlug.has(entry.page)) {
         add("error", "manifest", `${name} points at unknown page ${entry.page}.`);
      }
   }

   // Pages and routes must agree too: a page cannot document a removed route.
   for (const page of pages) {
      for (const route of page.routes) {
         if (!routeNames.has(route)) {
            add("error", "pages", `Page ${page.slug} lists unknown route ${route}.`);
         }
      }
      if (!["draft", "published"].includes(page.status)) {
         add("error", "pages", `Page ${page.slug} has unknown status ${page.status}.`);
      }
   }

   // 4. Published pages must have at least one captured image.
   for (const page of pages) {
      if (page.status !== "published") continue;
      if (pageImages(page.slug).length === 0) {
         add("error", "artifacts", `Published page ${page.slug} has no screenshots.`);
      }
   }

   // 5. Markdown image links resolve.
   for (const file of markdownFiles(guideDir)) {
      const markdown = stripCode(fs.readFileSync(file, "utf8"));
      IMAGE_LINK.lastIndex = 0;
      for (const match of markdown.matchAll(IMAGE_LINK)) {
         const target = match[1];
         if (/^(https?:|data:)/.test(target)) continue;
         const resolved = path.resolve(path.dirname(file), target);
         if (!fs.existsSync(resolved)) {
            add(
               "error",
               "links",
               `${relative(file)} references missing image ${target}.`
            );
         }
      }
   }

   // 5b. Markdown links between guide pages resolve.
   const MD_LINK = /\[[^\]]*\]\(([^)\s]+)\)/g;
   for (const file of markdownFiles(guideDir)) {
      const markdown = stripCode(fs.readFileSync(file, "utf8"));
      MD_LINK.lastIndex = 0;
      for (const match of markdown.matchAll(MD_LINK)) {
         const target = match[1];
         if (/^(https?:|mailto:|#)/.test(target)) continue;
         const filePart = target.split("#")[0];
         if (!filePart.endsWith(".md")) continue;
         const resolved = path.resolve(path.dirname(file), filePart);
         if (!fs.existsSync(resolved)) {
            add("error", "links", `${relative(file)} links to missing page ${filePart}.`);
         }
      }
   }

   // 5c. Generated blocks are intact, belong to their page, and have a story.
   const storySlots = new Map();
   for (const story of stories) {
      if (!storySlots.has(story.page)) storySlots.set(story.page, new Set());
      storySlots.get(story.page).add(story.slot ?? 1);
   }
   for (const file of markdownFiles(guideDir)) {
      const pageSlug = path.basename(file, ".md");
      const markdown = fs.readFileSync(file, "utf8");
      MARKER.lastIndex = 0;
      for (const match of markdown.matchAll(MARKER)) {
         const slug = match[1];
         const hash = match[3];
         const content = match[4];
         const slot = Number(match[2] ?? 1);
         if (slug === pageSlug && !storySlots.get(pageSlug)?.has(slot)) {
            add(
               "error",
               "blocks",
               `${relative(file)} has a generated block for slot ${slot}, but no story writes it.`
            );
         }
         if (slug !== pageSlug) {
            add(
               "error",
               "blocks",
               `${relative(file)} contains a block for ${slug}; regenerate the page instead.`
            );
         }
         if (!hash) {
            add("error", "blocks", `${relative(file)} has a block without a content hash.`);
         } else if (hashContent(content) !== hash) {
            add(
               "error",
               "blocks",
               `${relative(file)} has a hand-edited generated block (${slug}). Edit the story and re-capture.`
            );
         }
      }
   }

   // 6. The committed inventory matches the route source exactly.
   const inventoryFile = path.join(repoRoot, "tools", "docs-capture", "inventory.generated.json");
   const committed = fs.readFileSync(inventoryFile, "utf8");
   if (committed !== serializeInventory(inventory)) {
      add(
         "error",
         "inventory",
         "inventory.generated.json is stale. Run `pnpm docs:inventory`."
      );
   }

   // 7. Every sidebar route is reachable from at least one story.
   const pageIdsWithStories = new Set(stories.map((story) => story.page));
   const flowIds = new Set(stories.filter((story) => story.flow).map((story) => story.id));
   const reportedGaps = new Set();
   for (const route of inventory.routes) {
      if (!route.sidebar || route.hidden || route.adminOnly) continue;
      const page = pages.find((candidate) => candidate.routes.includes(route.name));
      if (!page) {
         add("error", "flows", `Sidebar route ${route.name} is not on any page.`);
         continue;
      }
      if (!pageIdsWithStories.has(page.slug)) {
         if (reportedGaps.has(page.slug)) continue;
         reportedGaps.add(page.slug);
         add(
            strict ? "error" : "warn",
            "flows",
            `Page ${page.slug} has no story yet (${route.name} and siblings).`
         );
      }
   }

   // 8. User-guide prose stays free of contributor vocabulary.
   for (const file of markdownFiles(guideDir)) {
      const markdown = stripFencedBlocks(fs.readFileSync(file, "utf8"));
      for (const token of FORBIDDEN_IN_GUIDE) {
         if (token.pattern.test(markdown)) {
            add(
               "error",
               "audience",
               `${relative(file)} contains contributor vocabulary "${token.label}".`
            );
         }
      }
   }

   // 9. Screenshots belong to the guide, not to architecture docs.
   for (const dir of ["ai", "development"].map((name) => path.join(docsDir, name))) {
      for (const file of markdownFiles(dir)) {
         const markdown = stripCode(fs.readFileSync(file, "utf8"));
         if (IMAGE_LINK.test(markdown)) {
            add(
               "error",
               "audience",
               `${relative(file)} embeds a screenshot; move it to docs/user-guide.`
            );
         }
         IMAGE_LINK.lastIndex = 0;
      }
   }

   // 10. No credential-shaped strings in committed docs or transcripts.
   const credentialCandidates = [
      ...textFiles(docsDir, [".md"]),
      ...textFiles(path.join(repoRoot, "tools", "docs-capture"), [".json", ".md"])
   ].filter((file) => !file.includes("node_modules"));
   for (const file of credentialCandidates) {
      const text = fs.readFileSync(file, "utf8");
      for (const pattern of CREDENTIAL_PATTERNS) {
         if (pattern.test(text)) {
            add("error", "secrets", `${relative(file)} looks like it contains a credential.`);
            break;
         }
      }
   }

   // 11. Recorded clips exist and stay within the guide's size budget.
   if (fs.existsSync(mediaManifestFile)) {
      let media = null;
      try {
         media = JSON.parse(fs.readFileSync(mediaManifestFile, "utf8"));
      } catch (error) {
         add("error", "media", `media.generated.json is not valid JSON: ${error.message}`);
      }
      for (const item of media?.items ?? []) {
         for (const [label, relativePath] of [
            ["GIF", item.gif],
            ["MP4", item.mp4],
            ["poster", item.poster]
         ]) {
            if (!relativePath) continue;
            if (!fs.existsSync(path.join(repoRoot, relativePath))) {
               add(
                  "error",
                  "media",
                  `${item.id} is missing its ${label} at ${relativePath}. Run \`pnpm docs:media\`.`
               );
            }
         }
         if (item.gifBytes > MAX_MEDIA_BYTES) {
            add(
               "warn",
               "media",
               `${item.id} GIF is ${(item.gifBytes / 1024 / 1024).toFixed(1)} MB; ` +
                  `keep clips under ${MAX_MEDIA_BYTES / 1024 / 1024} MB.`
            );
         }
         if (item.durationSeconds > MAX_MEDIA_SECONDS) {
            add(
               "warn",
               "media",
               `${item.id} runs ${item.durationSeconds}s; keep clips under ${MAX_MEDIA_SECONDS}s.`
            );
         }
      }
   }

   // Story shape is validated separately from the artifact checks.
   for (const problem of validateStories(stories)) {
      add("error", "stories", problem);
   }

   // Orphan images are reported, never deleted by the check.
   const referenced = new Set();
   for (const file of markdownFiles(guideDir)) {
      const markdown = stripCode(fs.readFileSync(file, "utf8"));
      IMAGE_LINK.lastIndex = 0;
      for (const match of markdown.matchAll(IMAGE_LINK)) {
         referenced.add(path.resolve(path.dirname(file), match[1]));
      }
   }
   const allImages = walkFiles(assetsDir, (file) => file.endsWith(".png"));
   const orphans = allImages.filter((file) => !referenced.has(file));

   // 11. The guide records the workspace version that produced it.
   const metaFile = path.join(guideDir, "_meta.json");
   if (!fs.existsSync(metaFile)) {
      add("warning", "meta", "docs/user-guide/_meta.json is missing; run `docs:capture`.");
   } else {
      try {
         const meta = JSON.parse(fs.readFileSync(metaFile, "utf8"));
         const pkg = JSON.parse(
            fs.readFileSync(path.join(repoRoot, "package.json"), "utf8")
         );
         if (meta.capturedWith !== pkg.version) {
            add(
               "warning",
               "meta",
               `docs/user-guide/_meta.json was captured with ${meta.capturedWith}, ` +
                  `but the workspace is at ${pkg.version}; re-run \`docs:capture\`.`
            );
         }
      } catch (error) {
         add("error", "meta", `docs/user-guide/_meta.json is not valid JSON: ${error.message}`);
      }
   }

   const documented = inventory.routes.filter((route) => manifest[route.name]?.kind === "documented");
   const excluded = inventory.routes.filter((route) => manifest[route.name]?.kind === "excluded");

   return {
      errors,
      warnings,
      stats: {
         routes: inventory.routes.length,
         documented: documented.length,
         excluded: excluded.length,
         published: pages.filter((page) => page.status === "published").length,
         drafts: pages.filter((page) => page.status === "draft").length,
         stories: stories.length,
         flows: flowIds.size,
         images: allImages.length,
         orphans: orphans.length
      },
      orphans
   };
}
