/**
 * Flow: first run (before setup).
 *
 * `kontext serve` seeds a placeholder local profile, so the app usually
 * opens directly on the home page. `/setup` is the optional way to replace that
 * placeholder before adding data.
 *
 * Runs before `POST /setup` (stage `unconfigured`).
 */
export default {
   id: "flow:first-run",
   page: "01-install-and-start",
   stage: "unconfigured",
   flow: true,
   order: 10,
   goto: "/setup",
   steps: [
      {
         id: "setup-page",
         caption:
            "Kontext starts with a placeholder profile. Open `/setup` before you add any data to replace it with your own name and email.",
         target: (page) =>
            page.getByRole("heading", { name: "Set up Kontext Studio" })
      },
      {
         id: "profile",
         caption: "Enter a first name, an optional last name, and an email address.",
         before: async (page) => {
            await page.getByLabel("First name").fill("Raymond");
            await page.getByLabel("Last name").fill("Tang");
            await page.getByLabel("Email").fill("raymond.tang@example.com");
         },
         target: (page) => page.getByLabel("First name")
      },
      {
         id: "finish",
         caption:
            "Select **Create local profile**. Kontext stores the profile on this machine and signs you in.",
         target: (page) =>
            page.getByRole("button", { name: "Create local profile" })
      }
   ]
};
