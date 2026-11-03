import { CHAT_SESSION_ID } from "../../fixtures/chat.mjs";

/**
 * Screen: a recorded conversation.
 *
 * The transcript is replayed from the committed recording, so the answer, the
 * tool calls, and the artifact references are stable across runs.
 */
export default {
   id: "screen:chat-detail",
   page: "08-chat-with-an-agent",
   stage: "configured",
   order: 81,
   slot: 2,
   collapseSidebar: true,
   goto: `/project/local/chat/${CHAT_SESSION_ID}`,
   steps: [
      {
         id: "chat-detail",
         caption:
            "A session keeps the question, the answer, and the tool calls that produced it. Expand **Run Sub Agent** to see what the agent delegated and what came back.",
         before: async (page) => {
            await page.getByText("Revenue by country").first().waitFor({
               timeout: 60_000
            });
            const hide = page.getByTitle("Hide artifacts");
            if (await hide.isVisible().catch(() => false)) {
               await hide.click();
            }
            await page.waitForTimeout(600);
         },
         afterSanitize: async (page) => {
            await page
               .locator(".ant-bubble-list-scroll-box")
               .evaluate((element) => {
                  element.classList.remove("ant-bubble-list-autoscroll");
                  element.scrollTop = 0;
               });
         }
      },
      {
         id: "chat-artifacts",
         caption:
            "Artifacts the run created — charts, data tables, notebooks, and images — open beside the conversation, so you can inspect the result without leaving the chat.",
         before: async (page) => {
            await page.getByTitle("Show artifacts").click();
            await page.waitForTimeout(1200);
         }
      }
   ]
};
