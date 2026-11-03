import { blockIds } from "../../fixtures/notebooks.mjs";

const popover = (page) => page.locator(".ce-popover--opened").last();

const firstBlock = (page) =>
   page.locator(`[data-id="${blockIds.featureTour.header}"]`);

/**
 * Screen: inserting, arranging, and previewing notebook blocks.
 *
 * The plus and settings buttons belong to the Editor.js block toolbar and are
 * only visible on hover, so the story activates a block first.
 */
export default {
   id: "screen:notebook-editing",
   page: "05-work-with-notebooks",
   stage: "configured",
   slot: 5,
   order: 65,
   collapseSidebar: true,
   goto: "/project/local/files",
   steps: [
      {
         id: "insert-menu",
         caption:
            "Hover a block and select **+** to insert another block. The menu lists text, table, SQL, Python, chart, diagram, and image blocks.",
         before: async (page) => {
            await page.getByText("notebook-block-types.kontext").first().click();
            await page.waitForURL((url) => url.pathname.includes("/notebook/"));
            await page.getByRole("heading", { name: "Block types" }).waitFor();
            await firstBlock(page).hover();
            await page.locator(".ce-toolbar__plus").click();
            await page.waitForTimeout(600);
         }
      },
      {
         id: "block-actions",
         caption:
            "The block settings menu changes the block type and heading level, and moves it within the notebook.",
         before: async (page) => {
            await page.keyboard.press("Escape");
            await firstBlock(page).hover();
            await page.locator(".ce-toolbar__settings-btn").click();
            await page.waitForTimeout(600);
         }
      },
      {
         id: "preview-mode",
         caption:
            "**Preview** hides the editing controls and renders the notebook as a reader would see it. Select the pencil to return to editing.",
         before: async (page) => {
            await page.keyboard.press("Escape");
            const header = page
               .locator(".kontext-notebook-editor > div")
               .first();
            await header
               .getByRole("button")
               .filter({ hasNotText: "Save" })
               .first()
               .click();
            await page.waitForTimeout(800);
         }
      }
   ]
};
