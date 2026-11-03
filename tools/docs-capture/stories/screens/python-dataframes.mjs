import { blockIds } from "../../fixtures/notebooks.mjs";

/**
 * Screen: SQL results feeding Python blocks.
 *
 * `sql-and-python.kontext` holds a SQL block with the alias
 * `revenue_by_country` and a Python block that loads it with
 * `await kontext.load_data(...)`. Outputs are saved with the document, so the
 * screenshots show the state after reopening the notebook.
 */
export default {
   id: "screen:python-dataframes",
   page: "07-python-and-data-frames",
   stage: "configured",
   collapseSidebar: true,
   order: 80,
   goto: "/project/local/files",
   steps: [
      {
         id: "sql-alias",
         caption:
            "The SQL block keeps its result and binds it to the alias **revenue_by_country**.",
         before: async (page) => {
            await page.getByText("sql-and-python.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page
               .getByRole("heading", { name: "SQL and Python share data" })
               .waitFor();
         },
         target: (page) => page.locator(`[data-id="${blockIds.python.sql}"]`)
      },
      {
         id: "python-code",
         caption:
            'The Python block loads the result with `await kontext.load_data("revenue_by_country")`, adds a share column, and returns a dataframe. Python runs server-side in the project runtime.',
         target: (page) => page.locator(`[data-id="${blockIds.python.code}"]`)
      },
   ]
};
