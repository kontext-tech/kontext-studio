/**
 * Screen: editing a standalone chart.
 *
 * `revenue-by-country.chart` opens in the chart viewer. Its **Edit** action
 * exposes the chart type, field mapping, palette, and number format in the same
 * builder used by notebook chart blocks.
 */
export default {
   id: "screen:chart-settings",
   page: "06-chart-results",
   stage: "configured",
   slot: 2,
   order: 75,
   collapseSidebar: true,
   goto: "/project/local/files",
   steps: [
      {
         id: "edit-chart",
         caption:
            "Open a **.chart** file and select **Edit** to change its type, fields, palette, and number format.",
         before: async (page) => {
            const search = page.getByPlaceholder("Search files");
            await search.fill("revenue-by-country.chart");
            await search.press("Enter");
            await page.getByText("revenue-by-country.chart").first().click();
            await page.waitForURL((url) => url.pathname.includes("/chart/"));
            await page.getByRole("button", { name: "Edit", exact: true }).click();
            await page
               .getByRole("dialog")
               .getByText("Edit Chart Configuration")
               .waitFor();
            await page.waitForTimeout(600);
         }
      }
   ]
};
