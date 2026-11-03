/**
 * Documentation coverage manifest.
 *
 * Every entry in this object is a decision about a route. A route that is not
 * mentioned here fails `pnpm docs:check`, which is how a new screen is prevented
 * from shipping undocumented by accident.
 *
 * Excluded routes must carry a reason from EXCLUSION_REASONS. Documented routes
 * must point at a page declared in pages.mjs.
 */
export const EXCLUSION_REASONS = [
   "admin-only",
   "internal-redirect",
   "not-found",
   "third-party"
];

export const manifest = {
   LOCAL_SETUP: { kind: "documented", page: "01-install-and-start" },
   // /login bootstraps a local session and immediately redirects to HOME or
   // /setup. It has no stable screen of its own, so it is not a documented step.
   LOGIN: { kind: "excluded", reason: "internal-redirect" },

   HOME: { kind: "documented", page: "02-create-a-project" },
   PROJECT_CONSOLE: { kind: "documented", page: "15-project-overview" },
   PROJECT: { kind: "documented", page: "08-chat-with-an-agent" },

   PROJECT_CATALOGS: { kind: "documented", page: "03-connect-a-data-source" },
   PROJECT_FILES: { kind: "documented", page: "04-browse-and-open-files" },
   PROJECT_FILE_DETAIL: {
      kind: "documented",
      page: "04-browse-and-open-files"
   },

   PROJECT_NOTEBOOK_DETAIL: {
      kind: "documented",
      page: "05-work-with-notebooks"
   },
   PROJECT_DATA_TABLE_DETAIL: {
      kind: "documented",
      page: "05-work-with-notebooks"
   },
   PROJECT_CHART_DETAIL: { kind: "documented", page: "06-chart-results" },

   PROJECT_CHAT_SESSIONS: { kind: "documented", page: "08-chat-with-an-agent" },
   PROJECT_CHAT_SESSION_DETAIL: {
      kind: "documented",
      page: "08-chat-with-an-agent"
   },

   PROJECT_KNOWLEDGE: {
      kind: "documented",
      page: "09-ground-an-agent-in-knowledge"
   },
   PROJECT_KNOWLEDGE_DETAIL: {
      kind: "documented",
      page: "09-ground-an-agent-in-knowledge"
   },

   USER_MODEL_CONNECTIONS: {
      kind: "documented",
      page: "10-connect-a-model-provider"
   },

   ACCOUNT_SETTINGS: { kind: "documented", page: "11-account" },
   USER_PYTHON_ENVIRONMENT: {
      kind: "documented",
      page: "12-python-environment"
   },
   PROJECT_SETTINGS: { kind: "documented", page: "13-project-settings" },
   PROJECT_JOBS: { kind: "documented", page: "14-jobs" },

   PROJECTS: { kind: "excluded", reason: "internal-redirect" },
   CLIENT_LOGIN: { kind: "excluded", reason: "third-party" },
   PROJECT_QUERY_SESSIONS: { kind: "excluded", reason: "admin-only" },
   PROJECT_EVENTS: { kind: "excluded", reason: "admin-only" },
   NOT_FOUND: { kind: "excluded", reason: "not-found" }
};
