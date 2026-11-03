import { blockIds } from "../../fixtures/notebooks.mjs";

const charts = [
   ["line", "A **line** chart shows a measure over time; use it for trends."],
   ["bar", "A **bar** chart compares categories with horizontal bars, which stay readable with long labels."],
   ["column", "A **column** chart compares categories vertically."],
   ["area", "An **area** chart emphasizes volume or a running total."],
   ["pie", "A **pie** chart shows composition; keep it to a handful of slices."],
   ["scatter", "A **scatter** chart shows the relationship between two numeric measures."],
   ["dualAxes", "A **dual-axes** chart plots two measures with different scales."],
   ["funnel", "A **funnel** chart ranks stages or segments by size."],
   ["heatmap", "A **heatmap** shows intensity across two categories."],
   ["histogram", "A **histogram** shows the distribution of one numeric field."],
   ["radar", "A **radar** chart compares profiles across several dimensions."],
   ["stock", "A **stock** chart shows open, close, low, and high for each period."]
];

/**
 * Screen: every chart type in the gallery notebook.
 *
 * Each chart block carries its own configuration and inline data, so the
 * screenshot shows exactly what a reader gets when the notebook is reopened.
 */
export default {
   id: "screen:chart-gallery",
   page: "06-chart-results",
   stage: "configured",
   collapseSidebar: true,
   order: 70,
   goto: "/project/local/files",
   steps: [
      {
         id: "open-gallery",
         caption: "Open the chart gallery notebook from the project files.",
         before: async (page) => {
            await page.getByText("chart-gallery.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page.getByRole("heading", { name: "Chart gallery" }).waitFor();
            // Charts render asynchronously; wait for the first canvas before the
            // first screenshot so the image does not depend on load timing.
            const firstChart = page.locator(
               `[data-id="${blockIds.gallery.line}"]`
            );
            await firstChart.scrollIntoViewIfNeeded();
            await firstChart.locator("canvas, svg").first().waitFor({ state: "visible" });
            await page.waitForTimeout(800);
            await page.evaluate(() => window.scrollTo(0, 0));
         }
      },
      ...charts.map(([key, caption]) => ({
         id: `${key}-chart`,
         caption,
         target: (page) => page.locator(`[data-id="${blockIds.gallery[key]}"]`)
      }))
   ]
};
