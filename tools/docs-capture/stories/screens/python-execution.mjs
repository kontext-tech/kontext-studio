import { normalizeText } from "../../lib/browser.mjs";
import { blockIds } from "../../fixtures/notebooks.mjs";

const codeBlock = (page) =>
   page.locator(`[data-id="${blockIds.pythonExecution.code}"]`);

/**
 * Screen: executing a Python block and opening its managed run.
 *
 * The fixture block is self-contained: it builds a dataframe, computes a share
 * column, and prints it. That keeps execution independent of SQL alias
 * hydration while still showing the real run path.
 */
export default {
   id: "screen:python-execution",
   page: "07-python-and-data-frames",
   stage: "configured",
   needsWorker: true,
   stabilizeAfter: true,
   slot: 2,
   order: 82,
   collapseSidebar: true,
   goto: "/project/local/files",
   steps: [
      {
         id: "python-execute",
         caption:
            "Select **Run** on a Python block to execute it. The output is stored with the notebook and the block links to the managed **Run details**.",
         before: async (page) => {
            await page.getByText("python-execution.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            const block = codeBlock(page);
            await block.scrollIntoViewIfNeeded();
            await block.locator("button").first().click();
            await block
               .getByText("Run details", { exact: true })
               .waitFor({ timeout: 180_000 });
            await page.waitForTimeout(800);
         }
      },
      {
         id: "python-run-details",
         caption:
            "**Run details** reports the execution status, timing, actor, and parameters for the block run.",
         before: async (page) => {
            await codeBlock(page)
               .getByText("Run details", { exact: true })
               .click();
            await page.locator(".ant-drawer-content-wrapper").waitFor({
               state: "visible"
            });
            await page.waitForTimeout(800);
         },
         afterSanitize: async (page) => {
            await normalizeText(page, ".ant-drawer-content-wrapper", [
               [
                  "\\b\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\b",
                  "2026-02-16 09:00:00"
               ],
               ["\\blocal-worker@[^\\s]+", "local-worker"],
               ["\\b\\d{12,}\\b", "20260216090000"],
               ["\\b\\d+\\.\\d+s\\b", "0.1s"]
            ]);
         },
         screenshotTarget: (page) => page.locator(".ant-drawer-content-wrapper")
      }
   ]
};
