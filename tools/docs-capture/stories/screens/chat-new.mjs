import path from "node:path";

import { repoRoot } from "../../lib/paths.mjs";

/**
 * Screen: starting a new chat and staging an attachment.
 *
 * The composer is the `PROJECT` route, which has no other screenshot. Staging
 * a file shows the attachment tray without sending a message.
 */
export default {
   id: "screen:chat-new",
   page: "08-chat-with-an-agent",
   stage: "configured",
   slot: 3,
   order: 79,
   collapseSidebar: true,
   goto: "/project/local",
   steps: [
      {
         id: "new-chat",
         caption:
            "**New Chat** opens an empty conversation. The composer chooses the data source, the model, and the Python approval mode before the first message.",
         before: async (page) => {
            await page.getByRole("heading", { name: /^Hello, / }).waitFor();
            await page.waitForTimeout(800);
         }
      },
      {
         id: "chat-attachment",
         caption:
            "**Attach files** stages a data file for the conversation so the agent can query it alongside the project data.",
         before: async (page) => {
            await page.locator('input[type="file"]').setInputFiles(
               path.join(
                  repoRoot,
                  "tools",
                  "docs-capture",
                  "fixtures",
                  "attachment-query.csv"
               )
            );
            await page.getByText("attachment-query.csv").first().waitFor({
               timeout: 60_000
            });
            await page.waitForTimeout(800);
         }
      }
   ]
};
