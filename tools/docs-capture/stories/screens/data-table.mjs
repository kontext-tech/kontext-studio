/**
 * Screen: a saved data table.
 *
 * `monthly-revenue.dt` is uploaded by the fixture with embedded columns and rows,
 * so the page renders without running a query.
 */
export default {
   id: "screen:data-table",
   page: "05-work-with-notebooks",
   stage: "configured",
   slot: 3,
   order: 61,
   goto: "/project/local/files",
   steps: [
      {
         id: "data-table",
         caption:
            "A saved **.dt** data table opens in a read-only grid with its column types and row count.",
         before: async (page) => {
            const search = page.getByPlaceholder("Search files");
            await search.fill("monthly-revenue.dt");
            await search.press("Enter");
            await page.getByText("monthly-revenue.dt", { exact: true }).first().click();
            await page.waitForURL((url) => url.pathname.includes("/data-table/"));
         }
      }
   ]
};
