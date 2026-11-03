/** Screen: the project settings form. */
export default {
   id: "screen:project-settings",
   page: "13-project-settings",
   stage: "configured",
   order: 130,
   slot: 1,
   goto: "/project/local/settings",
   steps: [
      {
         id: "project-settings",
         caption:
            "**Project Settings** edits the project name and description. In local mode the Access & Permissions tab is hidden because the local profile owns every project.",
         before: async (page) => {
            await page.getByRole("heading", { name: "Project Settings" }).waitFor();
         },
         screenshotTarget: (page) => page.locator(".ant-card").first()
      }
   ]
};
