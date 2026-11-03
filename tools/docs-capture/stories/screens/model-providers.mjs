/**
 * Screen: model providers and the add-provider form.
 *
 * Capture seeds one connection (Ollama Cloud) with a placeholder key. The form
 * is opened but not submitted, so the screenshot never needs a real credential.
 */
export default {
   id: "screen:model-providers",
   page: "10-connect-a-model-provider",
   stage: "configured",
   order: 100,
   goto: "/llm-providers",
   steps: [
      {
         id: "model-providers",
         caption:
            "**LLM Providers** groups connections by provider type. Select a provider tab to see its connections; each card shows the model, whether it is the default, and which credentials are configured.",
         before: async (page) => {
            await page.getByRole("tab", { name: /Ollama Cloud/ }).click();
            await page
               .getByText("DeepSeek V4.1 Flash (Ollama Cloud)")
               .first()
               .waitFor();
         },
         target: (page) => page.locator(".ant-card").first()
      },
      {
         id: "add-provider",
         caption:
            "**Add Provider** chooses a provider type, a curated model, a display name, and the credentials or endpoint it needs. **Add Provider** in the dialog validates the connection before it becomes available.",
         before: async (page) => {
            await page.getByRole("button", { name: "Add Provider" }).click();
            await page.getByRole("dialog").waitFor({ state: "visible" });
            await page.waitForTimeout(800);
         }
      },
      {
         id: "edit-provider",
         caption:
            "**Edit** reopens a saved connection with its model, endpoint, and availability. Stored credentials are not shown; leave the field blank to keep them.",
         before: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
            await page.getByRole("button", { name: "Edit" }).first().click();
            await page
               .getByRole("dialog")
               .getByText("Edit Provider", { exact: true })
               .waitFor();
         },
         after: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
         }
      },
      {
         id: "provider-validation",
         caption:
            "Saving without a model or display name reports the missing fields in place, so nothing is stored until the connection is valid.",
         before: async (page) => {
            await page.getByRole("button", { name: "Add Provider" }).click();
            const dialog = page.getByRole("dialog");
            await dialog.waitFor({ state: "visible" });
            await dialog
               .getByRole("button", { name: "Add Provider" })
               .click();
            await dialog.getByText("Please enter or select a model").waitFor();
         },
         after: async (page) => {
            await page.getByRole("button", { name: "Cancel" }).click();
         }
      }
   ]
};
