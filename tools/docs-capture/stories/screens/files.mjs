import { normalizeText } from "../../lib/browser.mjs";

/**
 * Screen: project files and the detail view of a plain file.
 *
 * The fixture uploads two CSV files, a markdown note, a notebook, and a saved
 * data table, so the list is populated.
 */
export default {
   id: "screen:files",
   page: "04-browse-and-open-files",
   stage: "configured",
   order: 50,
   goto: "/project/local/files",
   steps: [
      {
         id: "file-list",
         caption:
            "**Files** lists everything stored in the project. Select a name to open it.",
         target: (page) => page.getByText("customers.csv", { exact: true })
      },
      {
         id: "add-menu",
         caption:
            "**Add** starts an upload or creates a notebook in the current folder.",
         before: async (page) => {
            await page.getByRole("button", { name: /^Add$/ }).click();
            await page.getByText("Upload Files", { exact: true }).waitFor();
         }
      },
      {
         id: "upload-dialog",
         caption:
            "**Upload Files** accepts a drag-and-drop or a file picker, shows the allowed types and size limit, and can overwrite a file with the same name.",
         before: async (page) => {
            await page.getByText("Upload Files", { exact: true }).click();
            await page
               .getByRole("dialog")
               .getByText("Click or drag files to this area to upload")
               .waitFor();
         }
      },
      {
         id: "file-search",
         caption:
            "Search filters by name, and the file-type filter narrows the list to notebooks, charts, data tables, or uploads.",
         before: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
            const search = page.getByPlaceholder("Search files");
            await search.fill("invoice-lines");
            await search.press("Enter");
            await page.getByText("invoice-lines.csv", { exact: true }).waitFor();
         },
         afterSanitize: async (page) => {
            await normalizeText(page, ".ant-table", [
               ["less than a minute ago", "9 months ago"],
               ["a few seconds ago", "9 months ago"]
            ]);
         }
      },
      {
         id: "file-folder",
         caption:
            "Folders group related files. The breadcrumb shows the current folder, and selecting **Root** returns to the project root.",
         before: async (page) => {
            const search = page.getByPlaceholder("Search files");
            await search.fill("");
            await search.press("Enter");
            await page.getByText("reports/", { exact: true }).click();
            await page.getByText("revenue-by-month.csv", { exact: true }).waitFor();
         }
      },
      {
         id: "delete-confirm",
         caption:
            "Select the trash icon on a file to delete it. Kontext asks for confirmation because deleting a file removes it from the project.",
         before: async (page) => {
            await page.getByText("Root", { exact: true }).click();
            await page.getByText("customers.csv", { exact: true }).waitFor();
            const row = page
               .getByText("customers.csv", { exact: true })
               .locator("xpath=ancestor::tr");
            await row.getByTitle("Delete file").click();
            await page.getByText("Delete File", { exact: true }).last().waitFor();
         },
         after: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
         }
      },
      {
         id: "file-detail",
         caption:
            "A file opens on its details page, which records its type, size, owner, and creation date.",
         before: async (page) => {
            await page.getByText("customers.csv", { exact: true }).first().click();
            await page.waitForURL((url) => url.pathname.includes("/file/"));
            // The detail view replaces a spinner once the file loads; capture
            // the loaded state, not the loading state.
            await page.getByText("Created Date", { exact: true }).waitFor();
         }
      }
   ]
};
