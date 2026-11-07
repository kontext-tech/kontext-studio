import { blockIds } from "../../fixtures/notebooks.mjs";

/**
 * Clip: a SQL block and its full editor.
 *
 * The fixture stack cannot execute this query: the notebook's query session
 * resolves catalog connections in the worker, which does not see the
 * user-owned Chinook connection. The clip therefore shows the stored query and
 * result and opens the full editor instead of re-running it.
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
      "A SQL block keeps its query and result inline. Open it in the full editor to read the query and its stored output side by side.",
   goto: "/project/local/files",
   collapseSidebar: true,
   trimStart: 1.2,
   fps: 15,
   width: 1200,
   steps: [
      {
         id: "sql-block",
         pause: 1800,
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
            await page.waitForTimeout(600);
         }
      },
      {
         id: "full-editor",
         pause: 2200,
         before: async (page, { click }) => {
            const block = page.locator(
               `[data-id="${blockIds.featureTour.sql}"]`
            );
            await click(
               block.getByRole("button", { name: "Open in full editor" })
            );
            await page.locator(".ant-drawer").waitFor({ state: "visible" });
            await page.waitForTimeout(600);
         }
      }
   ]
};
