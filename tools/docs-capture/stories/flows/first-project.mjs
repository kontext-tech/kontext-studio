/**
 * Flow: open the workspace and create a project.
 *
 * Runs after `POST /setup`. Covers the home dashboard and the project overview,
 * which is why both routes map to `02-create-a-project`.
 */
export default {
   id: "flow:first-project",
   page: "02-create-a-project",
   stage: "configured",
   flow: true,
   order: 30,
   goto: "/",
   steps: [
      {
         id: "open-create",
         caption: "Select **Create Project** on the home page.",
         target: (page) => page.getByRole("button", { name: "Create Project" }),
         after: async (page) => {
            await page.getByRole("button", { name: "Create Project" }).first().click();
            await page
               .getByRole("dialog")
               .getByLabel("Project Name")
               .waitFor({ state: "visible" });
         }
      },
      {
         id: "name-project",
         caption:
            "Give the project a name. Kontext derives the project code from it, and the code appears in the project URL.",
         before: async (page) => {
            await page.getByRole("dialog").getByLabel("Project Name").fill("Sales Analysis");
         },
         target: (page) => page.getByRole("dialog").getByLabel("Project Name")
      },
      {
         id: "confirm",
         caption: "Select **Create Project** in the dialog to open the new project.",
         target: (page) =>
            page.getByRole("dialog").getByRole("button", { name: "Create Project" }),
         after: async (page) => {
            await page
               .getByRole("dialog")
               .getByRole("button", { name: "Create Project" })
               .click();
            await page
               .getByText("Sales Analysis", { exact: false })
               .first()
               .waitFor({ state: "visible" });
         }
      },
      {
         id: "project-overview",
         caption:
            "The project overview collects data sources, files, notebooks, chats, and settings.",
         target: (page) => page.getByText("Data Sources", { exact: false }).first()
      }
   ]
};
