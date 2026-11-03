/**
 * Screen: project data sources.
 *
 * The fixture seeds one external SQLite connection and syncs it, so the page
 * shows a ready connection instead of an empty state. The wizard is opened and
 * captured but never submitted, so the screenshot cannot create a duplicate.
 */
export default {
   id: "screen:catalogs",
   page: "03-connect-a-data-source",
   stage: "configured",
   order: 40,
   goto: "/project/local/catalogs",
   steps: [
      {
         id: "connection-list",
         caption:
            "Each connected source shows its provider, readiness, and connection details. **Sync Now** refreshes its schema.",
         target: (page) => page.getByText("Chinook music store", { exact: true })
      },
      {
         id: "open-wizard",
         caption: "Select **New Data Source** to add another connection.",
         target: (page) => page.getByRole("button", { name: "New Data Source" }),
         after: async (page) => {
            await page.getByRole("button", { name: "New Data Source" }).click();
            await page.getByRole("dialog").waitFor({ state: "visible" });
         }
      },
      {
         id: "choose-provider",
         caption:
            "Choose a provider. External databases and file-based sources share the same wizard: provider, details, and review.",
         target: (page) => page.getByRole("dialog").getByLabel("Provider")
      },
      {
         id: "edit-source",
         caption:
            "**Edit** reopens the connection form with its saved values. Leave a stored secret blank to keep it.",
         before: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
            await page.getByRole("button", { name: "Edit" }).first().click();
            await page
               .getByRole("dialog")
               .getByText("Edit Data Source")
               .waitFor();
         },
         after: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
         }
      },
      {
         id: "delete-source",
         caption:
            "**Delete** removes the saved connection and its synced metadata after a confirmation, without touching the database itself.",
         before: async (page) => {
            await page.getByRole("button", { name: "Delete" }).first().click();
            await page
               .getByText("Delete Chinook music store?", { exact: true })
               .last()
               .waitFor();
         },
         after: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
         }
      }
   ]
};
