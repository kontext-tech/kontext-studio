import { blockIds } from "../../fixtures/notebooks.mjs";

/**
 * Clip: running a SQL block from the full editor.
 *
 * The fixture block already has a previous result, so the story waits for the
 * running tag to clear instead of the results table, which is present before
 * the new run starts.
 */
export default {
   id: "media:sql-run",
   kind: "media",
   page: "05-work-with-notebooks",
   stage: "configured",
   destination: "docs",
   order: 93,
   slot: 4,
   caption:
      "Open a SQL block in the full editor, run the query, and inspect the result without leaving the notebook.",
   goto: "/project/local/files",
   collapseSidebar: true,
   trimStart: 1.2,
   fps: 15,
   width: 1200,
   needsWorker: true,
   needsQuerySession: true,
   stabilizeAfter: true,
   steps: [
      {
         id: "open-editor",
         pause: 1600,
         before: async (page, { click }) => {
            await click(
               page.getByText("notebook-block-types.kontext").first()
            );
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page
               .getByRole("heading", { name: "Block types" })
               .waitFor({ timeout: 60_000 });
            const block = page.locator(
               `[data-id="${blockIds.featureTour.sql}"]`
            );
            await block.scrollIntoViewIfNeeded();
            await click(
               block.getByRole("button", { name: "Open in full editor" })
            );
            await page.locator(".ant-drawer").waitFor({ state: "visible" });
         }
      },
      {
         id: "execute-query",
         pause: 2000,
         before: async (page, { click }) => {
            const drawer = page.locator(".ant-drawer");
            const running = page.getByText(/^running/).first();
            await click(
               drawer.getByRole("button", { name: "Execute", exact: true })
            );
            // The DuckDB query can finish before the running tag paints, so
            // treat the visible state as a hint rather than a requirement.
            await running
               .waitFor({ state: "visible", timeout: 2_000 })
               .catch(() => {});
            await running
               .waitFor({ state: "hidden", timeout: 120_000 })
               .catch(() => {});
            await drawer
               .locator(".ant-table")
               .first()
               .waitFor({ state: "visible", timeout: 30_000 });
         }
      }
   ]
};
