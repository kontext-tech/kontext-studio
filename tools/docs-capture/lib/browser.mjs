/**
 * Playwright helpers for deterministic documentation screenshots.
 *
 * The callout is drawn by the capture harness rather than by a browser
 * extension, which is what makes Scribe-style focus boxes reproducible.
 */
import fs from "node:fs";
import path from "node:path";

import { chromium } from "@playwright/test";

import { repoRoot } from "./paths.mjs";

export const VIEWPORT = { width: 1440, height: 900 };

/**
 * Wall-clock at which every captured page renders `Date`.
 *
 * Relative timestamps ("9 months ago", "2 days ago") are computed in the
 * browser from `Date.now()`. Without a frozen clock, the same fixture renders
 * different text as real time passes, so the committed screenshots drift and
 * cannot be verified byte-for-byte. Timers keep running; only `Date` is fixed.
 */
export const CAPTURE_CLOCK = new Date("2026-11-03T04:22:52.000Z");

const CALLOUT_ID = "docs-capture-callout";

export async function launchBrowser() {
   return chromium.launch();
}

export async function openPage(browser, { launchToken } = {}) {
   const context = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: 2,
      colorScheme: "light",
      locale: "en-US",
      timezoneId: "UTC",
      reducedMotion: "reduce"
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
   page.setDefaultTimeout(15_000);
   await page.clock.setFixedTime(CAPTURE_CLOCK);
   if (process.env.DOCS_DEBUG === "1") {
      await page.addInitScript(() => {
         const original = console.error;
         console.error = (...args) => {
            original(
               ...args.map((value) =>
                  value && Array.isArray(value.issues) ? JSON.stringify(value.issues) : value
               )
            );
         };
      });
      page.on("console", async (message) => {
         const args = await Promise.all(
            message.args().map((arg) => arg.jsonValue().catch(() => null))
         );
         const detail = args
            .filter((value) => value !== null && value !== undefined)
            .map((value) =>
               typeof value === "string" ? value : JSON.stringify(value)
            )
            .join(" ");
         console.log(`[browser:${message.type()}] ${message.text()} ${detail}`.trim());
      });
      page.on("pageerror", (error) =>
         console.log(`[browser:pageerror] ${error.message}`)
      );
   }
   return { context, page };
}

export async function settle(page) {
   await page.waitForLoadState("domcontentloaded").catch(() => {});
   await page
      .waitForFunction(() => {
         const root = document.querySelector("#root");
         return Boolean(root && root.childElementCount > 0);
      })
      .catch(() => {});
   await page.waitForTimeout(400);
}

export async function navigate(page, baseUrl, target) {
   await page.goto(new URL(target, baseUrl).href, { waitUntil: "domcontentloaded" });
   await settle(page);
}

export async function highlight(page, locator) {
   await locator.scrollIntoViewIfNeeded();
   const box = await locator.boundingBox();
   if (!box) return false;
   await page.evaluate(
      ({ id, box }) => {
         document.getElementById(id)?.remove();
         const marker = document.createElement("div");
         marker.id = id;
         Object.assign(marker.style, {
            position: "fixed",
            zIndex: "2147483647",
            pointerEvents: "none",
            border: "3px solid #1677ff",
            borderRadius: "8px",
            boxShadow: "0 0 0 1px rgba(22,119,255,0.35)",
            left: `${box.x - 6}px`,
            top: `${box.y - 6}px`,
            width: `${box.width + 12}px`,
            height: `${box.height + 12}px`
         });
         document.body.appendChild(marker);
         return true;
      },
      { id: CALLOUT_ID, box }
   );
   return true;
}

export async function clearHighlight(page) {
   await page
      .evaluate((id) => {
         document.getElementById(id)?.remove();
      }, CALLOUT_ID)
      .catch(() => {});
}

/**
 * Normalize rendered text before a screenshot.
 *
 * - Replace the capture's temporary HOME with `~`, so resource paths stay
 *   readable and machine-specific temp directories never leak into the repo.
 * - Replace UUIDs with a stable placeholder. File, owner, and session ids are
 *   regenerated on every run, and some pages render them; docs should not churn
 *   because of an id.
 */
export async function sanitizeScreenshot(page, { homeDir } = {}) {
   await page
      .evaluate(
         ({ root, checkout }) => {
            const uuid =
               /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
            const walker = document.createTreeWalker(
               document.body,
               NodeFilter.SHOW_TEXT
            );
            const nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            for (const node of nodes) {
               let value = node.nodeValue;
               if (!value) continue;
               if (root && value.includes(root)) {
                  value = value.split(root).join("~");
               }
               // Tracebacks can include the checkout path when the capture runs
               // from a clone. Never publish the developer's directory layout.
               if (checkout && value.includes(checkout)) {
                  value = value.split(checkout).join("~/kontext-studio");
               }
               value = value.replace(uuid, "00000000-0000-4000-8000-000000000000");
               if (value !== node.nodeValue) node.nodeValue = value;
            }
         },
         { root: homeDir, checkout: repoRoot }
      )
      .catch(() => {});
}

/**
 * Replace rendered text inside one region with stable values.
 *
 * Job run timestamps, worker names, execution ids, and durations are generated
 * when a capture executes a real job. They are truthful at capture time but
 * would churn every generated image, so normalize them in the screenshot only.
 */
export async function normalizeText(page, selector, rules) {
   await page.locator(selector).evaluate((root, replacements) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
         let value = node.nodeValue;
         if (!value) continue;
         for (const [pattern, replacement] of replacements) {
            value = value.replace(new RegExp(pattern, "g"), replacement);
         }
         if (value !== node.nodeValue) node.nodeValue = value;
      }
   }, rules);
}

/** Scroll back to the top after a client-side navigation. */
export async function scrollToTop(page) {
   await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
}

export async function screenshot(page, file, { beforeCapture } = {}) {
   // Park the pointer before capturing: a leftover hover position renders
   // tooltips and chart crosshairs into the image, and it differs between runs.
   await page.mouse.move(0, 0).catch(() => {});
   await page.waitForTimeout(150);
   // Late fetches can render after the caller sanitized. Run the sanitizer once
   // more as close to the capture as possible.
   if (beforeCapture) await beforeCapture();
   fs.mkdirSync(path.dirname(file), { recursive: true });
   await page.screenshot({
      path: file,
      animations: "disabled",
      caret: "hide",
      fullPage: false
   });
}

/**
 * Capture one element instead of the viewport.
 *
 * Some screens are mostly empty space around a single card or drawer. Cropping
 * to the element makes the image readable without losing the controls that
 * belong to it.
 */
export async function screenshotElement(page, locator, file, { beforeCapture } = {}) {
   await page.mouse.move(0, 0).catch(() => {});
   await page.waitForTimeout(150);
   if (beforeCapture) await beforeCapture();
   fs.mkdirSync(path.dirname(file), { recursive: true });
   await locator.screenshot({
      path: file,
      animations: "disabled",
      caret: "hide"
   });
}

/**
 * Capture a rectangular region of the viewport.
 *
 * Use this when the element that belongs in the image is a page header plus a
 * content area rather than a single DOM node, and when cropping to one node
 * would drop controls that live in the header.
 */
export async function screenshotClip(page, clip, file, { beforeCapture } = {}) {
   await page.mouse.move(0, 0).catch(() => {});
   await page.waitForTimeout(150);
   if (beforeCapture) await beforeCapture();
   fs.mkdirSync(path.dirname(file), { recursive: true });
   await page.screenshot({
      path: file,
      clip,
      animations: "disabled",
      caret: "hide"
   });
}
