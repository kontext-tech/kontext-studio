import { normalizeText } from "../../lib/browser.mjs";

/**
 * Screen: the job list.
 *
 * The fixture seed queues catalog sync, lakehouse ingest, and document indexing
 * runs, and the worker completes them before capture starts.
 */
export default {
   id: "screen:project-jobs",
   page: "14-jobs",
   stage: "configured",
   needsWorker: true,
   order: 140,
   slot: 1,
   goto: "/project/local/jobs",
   steps: [
      {
         id: "project-jobs",
         caption:
            "**Jobs** lists background runs with their status, trigger, and timing. Filter by status or refresh the list.",
         before: async (page) => {
            await page.getByRole("heading", { name: "Jobs" }).waitFor();
            await page.waitForTimeout(800);
         },
         afterSanitize: async (page) => {
            // Relative times and run durations depend on when the capture ran.
            await normalizeText(page, ".ant-table", [
               ["less than a minute ago", "2 months ago"],
               ["a few seconds ago", "2 months ago"],
               ["\\b\\d+(?:\\.\\d+)?s\\b", "1.8s"]
            ]);
         }
      }
   ]
};
