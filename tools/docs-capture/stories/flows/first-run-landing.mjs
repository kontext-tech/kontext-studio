/**
 * Flow: the workspace after setup.
 *
 * Runs in the configured stage, after fixtures are seeded. Captured before the
 * project-creation flow so the home page still shows a single project.
 */
export default {
   id: "flow:first-run-landing",
   page: "01-install-and-start",
   stage: "configured",
   flow: true,
   order: 20,
   goto: "/",
   steps: [
      {
         id: "landing",
         caption:
            "Kontext opens your workspace with one project and the local profile you created.",
         target: (page) => page.getByRole("heading", { name: /^Hello, / })
      }
   ]
};
