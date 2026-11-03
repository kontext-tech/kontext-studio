/**
 * Screen: the curated knowledge concept list.
 *
 * Fixtures seed three Chinook concepts (a metric, an entity, and a join) so the
 * list, status tags, and verification dates are populated.
 */
export default {
   id: "screen:knowledge-list",
   page: "09-ground-an-agent-in-knowledge",
   stage: "configured",
   order: 90,
   slot: 1,
   goto: "/project/local/knowledge",
   steps: [
      {
         id: "knowledge-list",
         caption:
            "**Knowledge** holds the curated concepts an agent can cite: metric definitions, entities, joins, and golden queries. Each concept carries a type, status, tags, and the last verification date.",
         before: async (page) => {
            await page.getByRole("heading", { name: "Knowledge" }).waitFor();
            await page.getByText("Revenue", { exact: true }).first().waitFor();
         },
         target: (page) => page.getByText("Revenue", { exact: true }).first()
      }
   ]
};
