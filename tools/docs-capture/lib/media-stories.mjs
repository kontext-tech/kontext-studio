import { blockIds } from "../fixtures/notebooks.mjs";

const block = (page, id) => page.locator(`[data-id="${id}"]`);

/**
 * Hero tour of one notebook containing SQL, Python, and chart blocks.
 *
 * The fixture keeps every block's stored result, so the clip needs neither a
 * worker nor a model. `trimToReady` drops the file browser and starts the
 * recording on the notebook itself.
 */
export function notebookTourStory(colorScheme) {
   const variant = colorScheme === "dark" ? "dark" : "light";
   return {
      id: `media:notebook-tour-${variant}`,
      kind: "media",
      page: "05-work-with-notebooks",
      stage: "configured",
      destination: "site",
      order: colorScheme === "dark" ? 96 : 95,
      formats: ["mp4"],
      colorScheme,
      posterAt: 1,
      viewport: { width: 1200, height: 900 },
      width: 1200,
      fps: 15,
      goto: "/project/local/files",
      collapseSidebar: true,
      trimToReady: true,
      ready: async (page) => {
         await page.getByText("notebook-block-types.kontext").first().click();
         await page.waitForURL((url) => url.pathname.includes("/notebook/"));
         await page
            .getByRole("heading", { name: "Block types" })
            .waitFor({ timeout: 60_000 });
      },
      steps: [
         {
            id: "sql-result",
            pause: 2200,
            before: async (page) => {
               await block(page, blockIds.featureTour.sql).scrollIntoViewIfNeeded();
            }
         },
         {
            id: "python-output",
            pause: 2600,
            before: async (page) => {
               await block(page, blockIds.featureTour.code).scrollIntoViewIfNeeded();
            }
         },
         {
            id: "chart",
            pause: 2800,
            before: async (page, { pause }) => {
               await block(
                  page,
                  blockIds.featureTour.chart
               ).scrollIntoViewIfNeeded();
               await pause(600);
            }
         }
      ]
   };
}
