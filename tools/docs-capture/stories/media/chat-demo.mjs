import { CHAT_SESSION_ID } from "../../fixtures/chat.mjs";

/**
 * Clip: the docs home demo.
 *
 * Site destination only: the splash page embeds the MP4 with a poster frame,
 * so no GIF is encoded. The story starts on the finished conversation and
 * shows the chart and its data, which is the payoff the home page sells.
 */
export default {
   id: "media:chat-demo",
   kind: "media",
   page: "08-chat-with-an-agent",
   stage: "configured",
   destination: "site",
   order: 94,
   formats: ["mp4"],
   posterAt: 1.5,
   goto: `/project/local/chat/${CHAT_SESSION_ID}`,
   collapseSidebar: true,
   trimToReady: true,
   ready: async (page) => {
      await page.getByText("Revenue by country").first().waitFor({
         timeout: 60_000
      });
   },
   fps: 15,
   width: 1200,
   steps: [
      {
         id: "chart",
         pause: 2200,
         before: async (page, { click, pause }) => {
            const show = page.getByTitle("Show artifacts");
            if (await show.isVisible().catch(() => false)) {
               await click(show);
            }
            await page
               .getByRole("tab", { name: /Revenue by country/ })
               .waitFor({ state: "visible", timeout: 30_000 });
            await pause(1200);
         }
      },
      {
         id: "data",
         pause: 1800,
         before: async (page, { click }) => {
            await click(page.getByRole("tab", { name: "Data", exact: true }));
         }
      },
      {
         id: "back-to-chart",
         pause: 1400,
         before: async (page, { click }) => {
            await click(page.getByRole("tab", { name: "Chart", exact: true }));
         }
      }
   ]
};
