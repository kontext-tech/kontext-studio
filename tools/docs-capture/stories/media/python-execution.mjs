import { blockIds } from "../../fixtures/notebooks.mjs";

const codeBlock = (page) =>
   page.locator(`[data-id="${blockIds.pythonExecution.code}"]`);

/**
 * Clip: running a Python block and seeing its output in the notebook.
 *
 * The fixture block is self-contained, so the execution stays independent of
 * SQL alias hydration and finishes quickly enough for a short clip.
 */
export default {
   id: "media:python-execution",
   kind: "media",
   page: "07-python-and-data-frames",
   stage: "configured",
   destination: "docs",
   order: 91,
   slot: 3,
   caption:
      "Select **Run** on a Python block. The code executes in the project runtime and its output is stored with the notebook.",
   goto: "/project/local/files",
   collapseSidebar: true,
   needsWorker: true,
   stabilizeAfter: true,
   fps: 15,
   width: 1200,
   trimStart: 1.2,
   steps: [
      {
         id: "open-notebook",
         pause: 1400,
         before: async (page, { click }) => {
            await click(page.getByText("python-execution.kontext").first());
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            const block = codeBlock(page);
            await block.scrollIntoViewIfNeeded();
            await page.waitForTimeout(600);
         }
      },
      {
         id: "run-block",
         pause: 1800,
         before: async (page, { click }) => {
            const block = codeBlock(page);
            const running = block.getByText(/^running/);
            await click(block.locator("button").first());
            // The fixture ships with a completed run, so waiting for the
            // Run details link returns before the new execution starts. Watch
            // the running tag instead, then wait for the result.
            await running.waitFor({ state: "visible", timeout: 30_000 });
            await running.waitFor({ state: "hidden", timeout: 120_000 });
            await block
               .getByText("Run details", { exact: true })
               .waitFor({ timeout: 30_000 });
         }
      }
   ]
};
