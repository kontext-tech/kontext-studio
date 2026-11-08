/**
 * Clip: switching a chart's type in the editor.
 *
 * The chart file opens in the viewer; **Edit** exposes the builder where the
 * type change previews immediately. The story stops before saving so the
 * fixture file is unchanged.
 */
export default {
   id: "media:chart-types",
   kind: "media",
   page: "06-chart-results",
   stage: "configured",
   destination: "docs",
   order: 92,
   slot: 3,
   caption:
      "Select **Edit** on a chart and change its type. The preview updates before you save the file.",
   goto: "/project/local/files",
   collapseSidebar: true,
   trimStart: 1.2,
   fps: 15,
   width: 1200,
   steps: [
      {
         id: "open-chart",
         pause: 1400,
         before: async (page, { click }) => {
            const search = page.getByPlaceholder("Search files");
            await search.fill("revenue-by-country.chart");
            await search.press("Enter");
            await click(page.getByText("revenue-by-country.chart").first());
            await page.waitForURL((url) => url.pathname.includes("/chart/"));
            await page
               .getByRole("button", { name: "Edit", exact: true })
               .waitFor({ timeout: 60_000 });
         }
      },
      {
         id: "edit-chart",
         pause: 1400,
         before: async (page, { click }) => {
            await click(
               page.getByRole("button", { name: "Edit", exact: true })
            );
            await page
               .getByRole("dialog")
               .getByText("Edit Chart Configuration")
               .waitFor();
         }
      },
      {
         id: "line-chart",
         pause: 1800,
         before: async (page, { click }) => {
            const dialog = page.getByRole("dialog");
            await click(dialog.locator(".ant-select").first());
            await click(
               page
                  .locator(".ant-select-item-option")
                  .filter({ hasText: "Line Chart" })
                  .first()
            );
         }
      },
      {
         id: "area-chart",
         pause: 2200,
         before: async (page, { click }) => {
            const dialog = page.getByRole("dialog");
            await click(dialog.locator(".ant-select").first());
            await click(
               page
                  .locator(".ant-select-item-option")
                  .filter({ hasText: "Area Chart" })
                  .first()
            );
         }
      }
   ]
};
