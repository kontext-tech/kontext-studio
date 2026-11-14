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
   docsPreview,
   publishedUserGuidePages,
   repoUrl
} from "../site-manifest.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(siteRoot, "..");
const docsRoot = path.join(repoRoot, "docs");
const contentRoot = path.join(siteRoot, "src", "content", "docs");
const PREVIEW_BANNER =
   "Preview: Kontext Studio launches soon. Install commands will work once the package is published.";

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
      if (docsPreview) {
         return null;
      }
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
      ...(docsPreview
         ? ["banner:", `  content: ${JSON.stringify(PREVIEW_BANNER)}`]
         : []),
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
   const primaryAction = docsPreview
      ? { text: "Read the user guide", link: "user-guide/" }
      : { text: "Get started", link: "user-guide/install-and-start/" };
   const connectHref = docsPreview
      ? "user-guide/"
      : "user-guide/install-and-start/";
   const banner = docsPreview
      ? `banner:\n  content: ${JSON.stringify(PREVIEW_BANNER)}\n`
      : "";

   const body = `---
title: Home
description: "Kontext is a local-first conversational analytics workspace. Chat with your data on the model you prefer and get the SQL, charts, Python code, or notebooks behind each answer — reproducible, ready to re-run."
${banner}template: splash
hero:
  title: Kontext Studio Docs
  tagline: Chat with your data. Answers you can re-run.
  actions:
    - text: ${primaryAction.text}
      link: ${primaryAction.link}
      icon: right-arrow
      variant: primary
    - text: Developer guide
      link: develop/
      icon: open-book
      variant: secondary
---

<div class="home-shell">
  <figure class="home-demo">
    <div class="home-demo-frame">
      <div class="home-demo-chrome" aria-hidden="true">
        <span class="home-demo-dot"></span>
        <span class="home-demo-dot"></span>
        <span class="home-demo-dot"></span>
        <span class="home-demo-address"></span>
      </div>
      <video
        id="home-demo-video"
        src="media/chat-notebook-light.mp4"
        poster="media/chat-notebook-light-poster.png"
        data-light-src="media/chat-notebook-light.mp4"
        data-dark-src="media/chat-notebook-dark.mp4"
        data-light-poster="media/chat-notebook-light-poster.png"
        data-dark-poster="media/chat-notebook-dark-poster.png"
        width="1200"
        height="900"
        autoplay
        loop
        muted
        playsinline
        aria-label="A chat answer beside the SQL, chart, and Python notebook it produced"
      ></video>
      <img
        id="home-demo-poster"
        src="media/chat-notebook-light-poster.png"
        data-light-src="media/chat-notebook-light-poster.png"
        data-dark-src="media/chat-notebook-dark-poster.png"
        alt="A chat answer beside the SQL, chart, and Python notebook it produced"
        class="home-demo-poster"
        width="1200"
        height="900"
      />
    </div>
    <figcaption>Ask a question. The answer comes with the SQL, chart, Python code, or reproducible notebook.</figcaption>
  </figure>

  <section class="home-section" aria-labelledby="home-features-title">
    <header class="home-section-head">
      <span class="home-eyebrow">What you can do</span>
      <h2 id="home-features-title">One workspace from question to answer you can re-run.</h2>
      <p>Agents plan the work, query your sources, and leave behind SQL, charts, Python code, or notebooks you can inspect and re-run.</p>
    </header>
    <div class="home-feature-grid">
      <a class="home-feature" href="user-guide/chat-with-an-agent/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.5 8.9 8.9 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.4 8.4 0 0 1 21 11.5Z"/></svg>
        </span>
        <strong>Agent chat</strong>
        <span>A coordinator delegates to SQL, chart, notebook, and Python specialists, with every tool call visible.</span>
      </a>
      <a class="home-feature" href="user-guide/work-with-notebooks/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5v-13Z"/><path d="M8 3v18"/></svg>
        </span>
        <strong>Reproducible notebooks</strong>
        <span>Mix prose, SQL, Python, charts, tables, and diagrams in one document that saves its results.</span>
      </a>
      <a class="home-feature" href="user-guide/connect-a-data-source/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>
        </span>
        <strong>SQL and your sources</strong>
        <span>Query the managed local lakehouse plus DuckDB, SQLite, PostgreSQL, and MySQL connections.</span>
      </a>
      <a class="home-feature" href="user-guide/chart-results/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/></svg>
        </span>
        <strong>Charts</strong>
        <span>Turn a result into a saved chart with its data, configuration, and editor kept together.</span>
      </a>
      <a class="home-feature" href="user-guide/python-and-data-frames/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/></svg>
        </span>
        <strong>Python and data frames</strong>
        <span>Run Python blocks that load SQL results by alias, without re-querying the source.</span>
      </a>
      <a class="home-feature" href="user-guide/connect-a-model-provider/">
        <span class="home-feature-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 5 6v5c0 4.4 3 7.6 7 10 4-2.4 7-5.6 7-10V6l-7-3Z"/><path d="m9.5 12 1.8 1.8 3.4-3.6"/></svg>
        </span>
        <strong>Local-first and your models</strong>
        <span>Run the app, API, worker, and kernels on your machine; bring Ollama, LM Studio, or a cloud provider.</span>
      </a>
    </div>
  </section>

  <section class="home-quickstart" aria-labelledby="home-quickstart-title">
    <div class="home-quickstart-copy">
      <span class="home-eyebrow">Quick start</span>
      <h2 id="home-quickstart-title">Run it on your machine in two commands.</h2>
      <p>Install from PyPI, start the local server, and open the workspace. Your files, project database, and kernels stay on your machine.</p>
      <a class="home-button" href="${connectHref}">Read the install guide</a>
    </div>
    <div class="home-terminal" aria-label="Terminal commands">
      <div class="home-terminal-bar" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <pre><code><span class="home-terminal-prompt">$</span> uv tool install kontext-studio
<span class="home-terminal-prompt">$</span> kontext serve</code></pre>
    </div>
  </section>

  <nav class="home-links" aria-label="Documentation">
    <a class="home-link" href="user-guide/">User guide <span aria-hidden="true">→</span></a>
    <a class="home-link" href="develop/">Developer guide <span aria-hidden="true">→</span></a>
  </nav>

</div>

<script>
  document.addEventListener("DOMContentLoaded", () => {
    const video = document.getElementById("home-demo-video");
    const poster = document.getElementById("home-demo-poster");
    if (!video || !poster) return;
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reduceMotion) {
      video.style.display = "none";
      poster.style.display = "block";
    }
    const applyTheme = () => {
      const dark = document.documentElement.dataset.theme === "dark";
      const videoSrc = video.dataset[dark ? "darkSrc" : "lightSrc"];
      const posterSrc = video.dataset[dark ? "darkPoster" : "lightPoster"];
      if (video.getAttribute("src") !== videoSrc) {
        video.src = videoSrc;
        video.poster = posterSrc;
        video.load();
        if (!reduceMotion) void video.play().catch(() => {});
      }
      poster.src =
        poster.dataset[dark ? "darkSrc" : "lightSrc"] || posterSrc;
    };
    applyTheme();
    new MutationObserver(applyTheme).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"]
    });
  });
</script>
`;

   fs.writeFileSync(path.join(contentRoot, "index.md"), body);
}

function writeDeveloperIndex() {
   // Preview builds do not link out to GitHub while the repository is private.
   const repoLink = (label, file) =>
      docsPreview
         ? `\`${file}\``
         : `[${label}](${repoUrl}/blob/main/${file})`;
   const lines = [
      "---",
      'title: "Developer guide"',
      'description: "Architecture and repository workflows for people contributing to Kontext."',
      ...(docsPreview
         ? ["banner:", `  content: ${JSON.stringify(PREVIEW_BANNER)}`]
         : []),
      "---",
      "",
      "These pages explain how Kontext is put together and how to work in this",
      "repository. They assume a checkout.",
      "",
      "## Getting started",
      "",
      `- ${repoLink("Contributing guide", "CONTRIBUTING.md")} — prerequisites, local setup, common commands, and the pull request process.`,
      `- ${repoLink("Agent guide", "AGENTS.md")} — the canonical architecture and conventions reference.`,
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
