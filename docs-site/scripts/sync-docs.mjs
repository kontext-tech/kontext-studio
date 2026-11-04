/**
 * Assemble the published docs site from `docs/`.
 *
 * The Markdown under `docs/` is the source of truth. This script generates the
 * Starlight content collection:
 *
 * - user-guide pages from the capture registry, with numeric filename prefixes
 *   removed from public URLs
 * - approved developer reference pages from `site-manifest.mjs`
 * - frontmatter, clean titles, and links rewritten to site routes or GitHub
 * - screenshots copied beside the user-guide pages
 *
 * Generated content is gitignored; run `pnpm docs:site:build` to regenerate it.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
   cleanUserGuideSlug,
   developerDocs,
   developerPagesByGroup,
   publishedUserGuidePages,
   repoUrl
} from "../site-manifest.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(siteRoot, "..");
const docsRoot = path.join(repoRoot, "docs");
const contentRoot = path.join(siteRoot, "src", "content", "docs");

const entries = [
   {
      source: path.join(docsRoot, "user-guide", "README.md"),
      route: "user-guide",
      index: true,
      title: "User guide",
      description:
         "Install Kontext, set up a profile, and work with projects, data sources, notebooks, and chats."
   },
   ...publishedUserGuidePages.map((page) => ({
      source: path.join(docsRoot, "user-guide", `${page.slug}.md`),
      route: `user-guide/${cleanUserGuideSlug(page.slug)}`,
      title: page.title,
      description: page.summary
   })),
   ...developerDocs.map((doc) => ({
      source: path.join(docsRoot, doc.source),
      route: doc.route,
      title: doc.title,
      description: doc.description
   }))
];

const routeBySource = new Map(
   entries.map((entry) => [path.resolve(entry.source), entry.route])
);

const warnings = [];

function stripLeadingTitle(body) {
   const lines = body.split("\n");
   const first = lines.findIndex((line) => line.trim() !== "");
   if (first >= 0 && /^#\s+/.test(lines[first])) {
      lines.splice(first, 1);
   }
   return lines.join("\n").replace(/^\n+/, "");
}

function stripCaptureMarkers(body) {
   return body.replace(
      /^\s*<!--\s*\/?docs:capture\b[^>]*-->\s*$/gm,
      ""
   );
}

function relativeRoute(fromRoute, toRoute) {
   // Starlight serves pages at trailing-slash URLs, so a page route is also
   // the directory relative links resolve from.
   const relative = path.posix.relative(fromRoute, toRoute);
   const url =
      relative === "" ? "./" : relative.startsWith(".") ? relative : `./${relative}`;
   return url.endsWith("/") ? url : `${url}/`;
}

function rewriteTarget(sourceFile, sourceRoute, href) {
   if (
      href.startsWith("http://") ||
      href.startsWith("https://") ||
      href.startsWith("mailto:")
   ) {
      return href;
   }

   const hashIndex = href.indexOf("#");
   const pathname = hashIndex >= 0 ? href.slice(0, hashIndex) : href;
   const hash = hashIndex >= 0 ? href.slice(hashIndex) : "";

   if (pathname === "") {
      return href;
   }

   const target = path.resolve(path.dirname(sourceFile), pathname);
   const route = routeBySource.get(target);
   if (route) {
      return `${relativeRoute(sourceRoute, route)}${hash}`;
   }

   if (fs.existsSync(target)) {
      const repoPath = path.relative(repoRoot, target).split(path.sep).join("/");
      return `${repoUrl}/blob/main/${repoPath}${hash}`;
   }

   if (pathname.endsWith(".md")) {
      warnings.push(
         `${path.relative(repoRoot, sourceFile)} links to unpublished ${pathname}`
      );
      return null;
   }

   warnings.push(
      `${path.relative(repoRoot, sourceFile)} links to missing ${pathname}`
   );
   return href;
}

function rewriteLinks(sourceFile, sourceRoute, body) {
   return body.replace(
      /(?<!!)\[([^\]]*)\]\(([^)\s]+)(\s+"[^"]*")?\)/g,
      (match, text, href, title = "") => {
         const rewritten = rewriteTarget(sourceFile, sourceRoute, href);
         if (rewritten === null) {
            return text;
         }
         return `[${text}](${rewritten}${title})`;
      }
   );
}

function frontmatter({ title, description }) {
   return [
      "---",
      `title: ${JSON.stringify(title)}`,
      `description: ${JSON.stringify(description)}`,
      "---",
      ""
   ].join("\n");
}

function writeEntry(entry) {
   const raw = fs.readFileSync(entry.source, "utf8");
   const body = rewriteLinks(
      entry.source,
      entry.route,
      stripCaptureMarkers(stripLeadingTitle(raw))
   );
   const target = path.join(
      contentRoot,
      `${entry.route}${entry.index ? "/index" : ""}.md`
   );
   fs.mkdirSync(path.dirname(target), { recursive: true });
   fs.writeFileSync(target, `${frontmatter(entry)}${body.trimEnd()}\n`);
}

function writeHomePage() {
   const body = `---
title: Home
description: "Kontext Labs documentation: install the local workspace, connect data and model providers, and work with notebooks, agents, and jobs."
template: splash
hero:
  title: Kontext Labs Docs
  tagline: Connect your data, bring your own LLM provider, and go from data questions to SQL, charts, and automated workflows — all in one workspace.
  actions:
    - text: User guide
      link: user-guide/
      icon: right-arrow
      variant: primary
    - text: Developer guide
      link: develop/
      icon: open-book
---

Kontext Labs is the AI-native workspace for data analysis. Connect your data,
bring your own LLM provider, and go from data questions to SQL, charts, and
automated workflows — all in one workspace.
`;

   fs.writeFileSync(path.join(contentRoot, "index.md"), body);
}

function writeDeveloperIndex() {
   const lines = [
      "---",
      'title: "Developer guide"',
      'description: "Architecture and repository workflows for people contributing to Kontext."',
      "---",
      "",
      "These pages explain how Kontext is put together and how to work in this",
      "repository. They assume a checkout and the toolchains described in the",
      `[agent guide](${repoUrl}/blob/main/AGENTS.md).`,
      ""
   ];

   for (const group of developerPagesByGroup) {
      lines.push(`## ${group.label}`, "");
      for (const doc of group.docs) {
         lines.push(
            `- [${doc.title}](${relativeRoute("develop", doc.route)}) — ${doc.description}`
         );
      }
      lines.push("");
   }

   fs.writeFileSync(path.join(contentRoot, "develop", "index.md"), lines.join("\n"));
}

function copyAssets() {
   const source = path.join(docsRoot, "user-guide", "assets");
   const target = path.join(contentRoot, "user-guide", "assets");
   fs.cpSync(source, target, { recursive: true });
}

fs.rmSync(contentRoot, { recursive: true, force: true });
fs.mkdirSync(contentRoot, { recursive: true });

for (const entry of entries) {
   if (!fs.existsSync(entry.source)) {
      throw new Error(
         `Missing source document: ${path.relative(repoRoot, entry.source)}`
      );
   }
   writeEntry(entry);
}

writeHomePage();
writeDeveloperIndex();
copyAssets();

if (warnings.length > 0) {
   console.warn(
      `[docs-site] rewrote ${warnings.length} link${warnings.length === 1 ? "" : "s"} without a published target:`
   );
   for (const warning of warnings) {
      console.warn(`  ${warning}`);
   }
}

console.log(
   `[docs-site] synced ${entries.length} pages and ${
      fs.readdirSync(path.join(contentRoot, "user-guide", "assets")).length
   } asset directories into ${path.relative(repoRoot, contentRoot)}.`
);
