import { blockIds } from "../../fixtures/notebooks.mjs";

const block = (id) => (page) => page.locator(`[data-id="${id}"]`);

/**
 * Screen: notebook block types.
 *
 * `notebook-block-types.kontext` contains one example of every content block.
 * Image-picker blocks select from the resource library and are documented on the
 * page rather than rendered here.
 */
export default {
   id: "screen:notebook-blocks",
   page: "05-work-with-notebooks",
   stage: "configured",
   collapseSidebar: true,
   order: 60,
   goto: "/project/local/files",
   steps: [
      {
         id: "structure",
         caption:
            "A notebook is an ordered list of typed blocks. Text blocks cover headings, paragraphs, lists, and quotes.",
         before: async (page) => {
            await page.getByText("notebook-block-types.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page.getByRole("heading", { name: "Block types" }).waitFor();
         },
         target: block(blockIds.featureTour.header)
      },
      {
         id: "table",
         caption:
            "Table blocks hold static rows with an optional header row. They are useful for short reference tables that do not need a query.",
         target: block(blockIds.featureTour.table)
      },
      {
         id: "sql",
         caption:
            "A SQL block keeps its query, its result, and a notebook-scoped alias in the document.",
         target: block(blockIds.featureTour.sql)
      },
      {
         id: "python",
         caption:
            "A Python block runs code and keeps its output. The SQL alias from the previous block is available without re-running the query.",
         target: block(blockIds.featureTour.code)
      },
      {
         id: "diagram",
         caption:
            "Mermaid blocks render diagrams from text, so architecture notes stay editable.",
         target: block(blockIds.featureTour.mermaid)
      },
      {
         id: "image",
         caption: "Image blocks embed a file with an optional caption and border.",
         target: block(blockIds.featureTour.image)
      }
   ]
};
