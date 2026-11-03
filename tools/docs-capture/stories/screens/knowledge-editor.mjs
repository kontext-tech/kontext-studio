/**
 * Screen: the concept editor.
 *
 * A separate story so the editor sits under the "create or edit" section of the
 * page rather than at the end of the concepts list.
 */
export default {
   id: "screen:knowledge-editor",
   page: "09-ground-an-agent-in-knowledge",
   stage: "configured",
   order: 91,
   slot: 2,
   goto: "/project/local/knowledge",
   steps: [
      {
         id: "concept-editor",
         caption:
            "**New Concept** opens the editor: id, type, status, title, description, resource, tags, body, and the freshness window. The id is the stable path agents and links use.",
         before: async (page) => {
            await page.getByRole("button", { name: "New Concept" }).click();
            await page.getByRole("dialog").waitFor({ state: "visible" });
            await page.waitForTimeout(800);
         }
      }
   ]
};
