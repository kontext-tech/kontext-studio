import { blockIds } from "../../fixtures/notebooks.mjs";

/**
 * Screen: the SQL block's full editor drawer.
 *
 * The inline block shows the query summary and result; the code icon opens the
 * full editor with the SQL, the catalog scope, and the run controls.
 */
export default {
   id: "screen:sql-drawer",
   page: "05-work-with-notebooks",
   stage: "configured",
   slot: 2,
   order: 62,
   collapseSidebar: true,
   goto: "/project/local/files",
   steps: [
      {
         id: "sql-drawer",
         caption:
            "Select the code icon on a SQL block to open the full editor. It shows the query, the catalog scope, and the run controls.",
         before: async (page) => {
            await page.getByText("notebook-block-types.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page.getByRole("heading", { name: "Block types" }).waitFor();
            const block = page.locator(`[data-id="${blockIds.featureTour.sql}"]`);
            await block.scrollIntoViewIfNeeded();
            await block.getByRole("button", { name: "Open in full editor" }).click();
            await page.locator(".ant-drawer").waitFor({ state: "visible" });
            await page.waitForTimeout(600);
         }
      }
   ]
};
