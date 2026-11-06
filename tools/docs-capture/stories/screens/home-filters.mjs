/**
 * Screen: finding a project on the home page.
 *
 * Runs after the first-project flow has created the second project, so the
 * filters have something to narrow.
 */
export default {
   id: "screen:home-filters",
   page: "02-create-a-project",
   stage: "configured",
   order: 31,
   slot: 2,
   goto: "/",
   steps: [
      {
         id: "project-search",
         caption:
            "The search box filters the project list by name. **Clear** removes the search and role filters.",
         before: async (page) => {
            await page.getByRole("heading", { name: /^Hello, / }).waitFor();
            const search = page.getByPlaceholder("Search projects...");
            await search.fill("Sales");
            await search.press("Enter");
            await page.getByText("Sales Analysis", { exact: true }).waitFor();
         }
      },
      {
         id: "project-role-filter",
         caption:
            "**Filter by role** limits the list to projects where you have a given role, such as owner, admin, contributor, or reader.",
         before: async (page) => {
            const search = page.getByPlaceholder("Search projects...");
            await search.fill("");
            await search.press("Enter");
            await page.locator(".ant-select-content").first().click();
            await page.getByTitle("Owner").click();
            await page.keyboard.press("Escape");
            await page.waitForTimeout(600);
         }
      }
   ]
};
