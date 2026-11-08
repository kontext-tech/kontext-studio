import { CHAT_SESSION_ID } from "../fixtures/chat.mjs";
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

/**
 * Hero clip for the platform site: the recorded chat answer and the notebook
 * artifact it produced, side by side.
 *
 * The notebook artifact is seeded from `revenue-notebook.kontext`, so the clip
 * shows the agent's answer and the SQL/chart/Python document it returned
 * without a model credential.
 */
export function chatNotebookHeroStory(colorScheme) {
   const variant = colorScheme === "dark" ? "dark" : "light";
   // The artifact panel uses a custom tab shell, so block ids are not inside
   // an Ant Design content holder. They are unique to the notebook.
   const notebookBlock = (page, id) =>
      page.locator(`[data-id="${id}"]`).first();

   return {
      id: `media:chat-notebook-${variant}`,
      kind: "media",
      page: "08-chat-with-an-agent",
      stage: "configured",
      destination: "site",
      order: colorScheme === "dark" ? 98 : 97,
      formats: ["mp4"],
      colorScheme,
      posterAt: 6,
      viewport: { width: 1200, height: 900 },
      width: 1200,
      fps: 15,
      goto: `/project/local/chat/${CHAT_SESSION_ID}`,
      collapseSidebar: true,
      trimToReady: true,
      ready: async (page) => {
         await page
            .getByText(
               "Which countries generate the most revenue in the music store"
            )
            .first()
            .waitFor({ timeout: 60_000 });
         // The artifact panel auto-opens and starts loading the chart. Hide it
         // and rewind the conversation before the clip is trimmed, so the hero
         // opens on the question rather than a spinner.
         const hide = page.getByTitle("Hide artifacts");
         await hide
            .waitFor({ state: "visible", timeout: 5_000 })
            .catch(() => {});
         if (await hide.isVisible().catch(() => false)) {
            await hide.click();
         }
         await page
            .locator(".ant-bubble-list-scroll-box")
            .evaluate((element) => {
               element.classList.remove("ant-bubble-list-autoscroll");
               element.scrollTop = 0;
            });
         await page.waitForTimeout(400);
      },
      steps: [
         {
            id: "answer",
            pause: 1800
         },
         {
            id: "notebook",
            pause: 2200,
            before: async (page, { click }) => {
               const show = page.getByTitle("Show artifacts");
               if (await show.isVisible().catch(() => false)) {
                  await click(show);
               }
               await click(
                  page.getByRole("tab", {
                     name: /Revenue by country notebook/
                  })
               );
               await notebookBlock(page, blockIds.featureTour.sql).waitFor({
                  state: "visible",
                  timeout: 30_000
               });
            }
         },
         {
            id: "sql",
            pause: 1800,
            before: async (page) => {
               await notebookBlock(
                  page,
                  blockIds.featureTour.sql
               ).scrollIntoViewIfNeeded();
            }
         },
         {
            id: "chart",
            pause: 1800,
            before: async (page) => {
               await notebookBlock(
                  page,
                  blockIds.featureTour.chart
               ).scrollIntoViewIfNeeded();
            }
         },
         {
            id: "python",
            pause: 2200,
            before: async (page) => {
               await notebookBlock(
                  page,
                  blockIds.featureTour.code
               ).scrollIntoViewIfNeeded();
            }
         }
      ]
   };
}
