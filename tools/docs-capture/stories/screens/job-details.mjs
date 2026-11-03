import { normalizeText } from "../../lib/browser.mjs";

/**
 * Screen: a completed job run's details, parameters, and logs.
 *
 * The Python execution story runs before this one, so the fixture has a real
 * successful run with logs to inspect.
 */
const drawer = (page) => page.locator(".ant-drawer-content-wrapper");

const normalizeRun = async (page) => {
   await normalizeText(page, ".ant-drawer-content-wrapper", [
      [
         "\\b\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\b",
         "2026-02-16 09:00:00"
      ],
      ["\\blocal-worker@[^\\s]+", "local-worker"],
      ["\\b\\d{12,}\\b", "20260216090000"],
      ["\\b\\d+(?:\\.\\d+)?ms\\b", "95ms"],
      ['"ExecutionTimeMs": \\d+', '"ExecutionTimeMs": 1255'],
      ["\\b\\d+\\.\\d+s\\b", "0.1s"]
   ]);
};

export default {
   id: "screen:job-details",
   page: "14-jobs",
   stage: "configured",
   needsWorker: true,
   requires: ["screen:python-execution"],
   order: 141,
   slot: 2,
   goto: "/project/local/jobs",
   steps: [
      {
         id: "job-details",
         caption:
            "Select the eye icon on a run to open **Job Run Details**. **Details** shows the status, timing, trigger, attempt count, execution id, and worker. The same drawer opens from a notebook block's **Run details** link.",
         before: async (page) => {
            // Full captures run the Python execution story first; a page-only
            // capture falls back to the seeded catalog run. Wait for the table
            // so the check does not run against an empty list.
            await page.getByText("External Catalog Initial Sync").first().waitFor();
            const runName =
               (await page.getByText("Execute Notebook Python").count()) > 0
                  ? "Execute Notebook Python"
                  : "External Catalog Initial Sync";
            const row = page
               .getByText(runName)
               .first()
               .locator("xpath=ancestor::tr");
            await row.getByRole("button").first().click();
            await drawer(page).waitFor({ state: "visible" });
            await page.waitForTimeout(800);
         },
         afterSanitize: normalizeRun,
         screenshotTarget: drawer
      },
      {
         id: "job-parameters",
         caption:
            "**Parameters** shows the payload the run was queued with, so you can check what a run was asked to do.",
         before: async (page) => {
            await page.getByRole("tab", { name: "Parameters" }).click();
            await page.waitForTimeout(500);
         },
         afterSanitize: normalizeRun,
         screenshotTarget: drawer
      },
      {
         id: "job-logs",
         caption:
            "**Logs** shows the run's log lines, including the captured output and timing for a Python execution.",
         before: async (page) => {
            await page.getByRole("tab", { name: "Logs" }).click();
            await page.waitForTimeout(800);
         },
         afterSanitize: normalizeRun,
         screenshotTarget: drawer
      }
   ]
};
