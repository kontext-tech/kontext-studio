import { CHAT_SESSION_ID } from "../../fixtures/chat.mjs";

/**
 * Clip: a recorded chat answer and the chart artifact it produced.
 *
 * The transcript is replayed from the committed recording, so the clip never
 * needs a provider credential and matches the screenshots on the same page.
 */
export default {
   id: "media:chat-chart",
   kind: "media",
   page: "08-chat-with-an-agent",
   stage: "configured",
   destination: "docs",
   order: 90,
   slot: 4,
   caption:
      "A session keeps the answer and the tool calls that produced it. Artifacts open beside the conversation, so the chart and its data are one click away.",
   goto: `/project/local/chat/${CHAT_SESSION_ID}`,
   collapseSidebar: true,
   fps: 15,
   width: 1200,
   trimToReady: true,
   ready: async (page) => {
      await page.getByText("Revenue by country").first().waitFor({
         timeout: 60_000
      });
   },
   steps: [
      {
         id: "answer",
         pause: 1600,
         before: async (page, { click }) => {
            await page.getByText("Revenue by country").first().waitFor({
               timeout: 60_000
            });
            // The artifact panel auto-opens once the artifacts load. Wait for
            // it so the hide is deliberate rather than racing the auto-open.
            const hide = page.getByTitle("Hide artifacts");
            await hide.waitFor({ state: "visible", timeout: 8_000 }).catch(() => {});
            if (await hide.isVisible().catch(() => false)) {
               await click(hide);
            }
            await page
               .locator(".ant-bubble-list-scroll-box")
               .evaluate((element) => {
                  element.classList.remove("ant-bubble-list-autoscroll");
                  element.scrollTop = 0;
               });
         }
      },
      {
         id: "artifacts",
         pause: 1800,
         before: async (page, { click, pause }) => {
            await click(page.getByTitle("Show artifacts"));
            await page
               .getByRole("tab", { name: /Revenue by country/ })
               .waitFor({ state: "visible" });
            // The chart renders asynchronously inside the selected tab; hold
            // long enough for the panel to finish laying out.
            await pause(1600);
         }
      },
      {
         id: "chart-data",
         pause: 1600,
         before: async (page, { click, pause }) => {
            await click(page.getByRole("tab", { name: "Data", exact: true }));
            await pause(1200);
         }
      }
   ]
};
