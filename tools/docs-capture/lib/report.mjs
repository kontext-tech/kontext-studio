import fs from "node:fs";
import path from "node:path";

import { assetsDir, toolsDir } from "./paths.mjs";
import { walkFiles } from "./guide.mjs";

function escapeHtml(value) {
   return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
}

export function writeReport() {
   const reportDir = path.join(toolsDir, "report");
   const images = walkFiles(assetsDir, (file) => file.endsWith(".png")).sort();
   const byPage = new Map();

   for (const image of images) {
      const slug = path.basename(path.dirname(image));
      if (!byPage.has(slug)) byPage.set(slug, []);
      byPage.get(slug).push(image);
   }

   const sections = [...byPage.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([slug, files]) => {
         const cards = files
            .map((file) => {
               const relative = path.relative(reportDir, file).split(path.sep).join("/");
               return [
                  '<figure>',
                  `<img src="${escapeHtml(relative)}" alt="${escapeHtml(path.basename(file, ".png"))}" loading="lazy" />`,
                  `<figcaption>${escapeHtml(path.relative(assetsDir, file))}</figcaption>`,
                  "</figure>"
               ].join("\n");
            })
            .join("\n");
         return `<section><h2>${escapeHtml(slug)}</h2><div class="grid">${cards}</div></section>`;
      })
      .join("\n");

   const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Kontext docs capture report</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2937; }
  h1 { margin: 0 0 8px; font-size: 20px; }
  p.meta { margin: 0 0 32px; color: #6b7280; font-size: 13px; }
  h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; color: #6b7280; margin: 32px 0 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  figure { margin: 0; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background: #fff; }
  img { display: block; width: 100%; height: auto; }
  figcaption { padding: 8px 10px; font-size: 12px; color: #6b7280; border-top: 1px solid #f3f4f6; }
  .empty { color: #6b7280; }
</style>
</head>
<body>
  <h1>Kontext docs capture report</h1>
  <p class="meta">${images.length} image${images.length === 1 ? "" : "s"} · generated ${new Date().toISOString()}</p>
  ${sections || '<p class="empty">No screenshots captured yet.</p>'}
</body>
</html>
`;

   fs.mkdirSync(reportDir, { recursive: true });
   const file = path.join(reportDir, "index.html");
   fs.writeFileSync(file, html);
   return file;
}
