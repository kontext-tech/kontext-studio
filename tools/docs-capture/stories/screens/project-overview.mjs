/** Screen: project stats and project details on the overview page. */
export default {
   id: "screen:project-overview",
   page: "15-project-overview",
   stage: "configured",
   order: 150,
   slot: 1,
   goto: "/project/local/console",
   steps: [
      {
         id: "project-stats",
         caption:
            "The **Project Stats** tab summarizes files, job duration, total tokens, storage usage, and monthly token history.",
         before: async (page) => {
            await page.getByRole("tab", { name: /Project Stats/ }).waitFor();
            await page.getByText("Total Used Tokens").waitFor();
            await page.getByText("Storage Usage").waitFor();
            await page.waitForTimeout(600);
         },
         screenshotTarget: (page) => page.locator(".ant-tabs").first()
      },
      {
         id: "project-details",
         caption:
            "The **Project Details** tab shows the project ID, code, creation date, and file-size limit.",
         before: async (page) => {
            await page.getByRole("tab", { name: /Project Details/ }).click();
            await page.getByText("Project Code").waitFor();
         },
         screenshotTarget: (page) => page.locator(".ant-tabs").first()
      }
   ]
};
