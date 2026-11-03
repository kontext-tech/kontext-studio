/** Screen: one curated concept in detail. */
export default {
   id: "screen:knowledge-detail",
   page: "09-ground-an-agent-in-knowledge",
   stage: "configured",
   order: 91,
   slot: 4,
   goto: "/project/local/knowledge/metrics/revenue",
   steps: [
      {
         id: "knowledge-detail",
         caption:
            "A concept page renders the Markdown body and records where it came from: the generating actor, the people who verified it, its sources, and when it should be reviewed again.",
         before: async (page) => {
            await page.getByRole("heading", { name: "Revenue" }).waitFor();
            await page.waitForTimeout(600);
         }
      }
   ]
};
