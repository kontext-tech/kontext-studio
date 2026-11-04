/**
 * Page registry for the user guide.
 *
 * `slug` is the page filename without the extension and is the stable identity
 * of a page: retitling a page never changes its slug, so links and image
 * directories survive.
 *
 * `status` gates artefact checks. A `draft` page is registered but has no
 * screenshots yet, which keeps the bootstrap tree green while the capture
 * harness is filled in. `pnpm docs:check --strict` treats drafts as failures and
 * is the mode CI uses once every page is captured.
 *
 * `flow` names the journey that makes this page reachable from the narrative.
 * Routes on a page with no flow are only documented as isolated reference
 * screens.
 *
 * `group` is the navigation group the page belongs to. It orders the guide
 * index and the published site sidebar. On the docs site, Starlight supplies
 * previous/next pagination, so pages do not carry their own "Next steps" links.
 */
export const pageGroups = [
   { id: "get-started", label: "Get started" },
   { id: "data", label: "Data" },
   { id: "notebooks", label: "Notebooks" },
   { id: "agents", label: "Agents and models" },
   { id: "workspace", label: "Workspace settings" }
];

export const pages = [
   {
      slug: "01-install-and-start",
      title: "Install and start Kontext Labs",
      group: "get-started",
      order: 1,
      status: "published",
      summary:
         "Install the released wheel, start the local server, and replace the placeholder profile.",
      routes: ["LOCAL_SETUP"],
      flow: "first-run"
   },
   {
      slug: "02-create-a-project",
      title: "Open or create a project",
      group: "get-started",
      order: 2,
      status: "published",
      summary: "Projects hold data sources, files, chats, and settings.",
      routes: ["HOME", "PROJECT_CONSOLE"],
      flow: "first-project"
   },
   {
      slug: "03-connect-a-data-source",
      title: "Connect a data source",
      group: "data",
      order: 3,
      status: "published",
      summary: "Connect an external database or inspect the internal lakehouse.",
      routes: ["PROJECT_CATALOGS"],
      flow: "first-data-source"
   },
   {
      slug: "04-browse-and-open-files",
      title: "Browse and manage files",
      group: "data",
      order: 4,
      status: "published",
      summary: "Upload, organize, search, and open project files.",
      routes: ["PROJECT_FILES", "PROJECT_FILE_DETAIL"],
      flow: "first-data-source"
   },
   {
      slug: "05-work-with-notebooks",
      title: "Work with notebooks",
      group: "notebooks",
      order: 5,
      status: "published",
      summary:
         "Use text, table, SQL, code, chart, diagram, and image blocks in one document.",
      routes: ["PROJECT_NOTEBOOK_DETAIL", "PROJECT_DATA_TABLE_DETAIL"],
      flow: "notebook-basics"
   },
   {
      slug: "06-chart-results",
      title: "Chart query results",
      group: "notebooks",
      order: 6,
      status: "published",
      summary: "Every chart type, with the data and configuration saved in the document.",
      routes: ["PROJECT_CHART_DETAIL"],
      flow: "notebook-charts"
   },
   {
      slug: "07-python-and-data-frames",
      title: "Python and data frames",
      group: "notebooks",
      order: 7,
      status: "published",
      summary:
         "Run Python blocks and load SQL results with kontext.load_data, without re-querying.",
      routes: ["PROJECT_NOTEBOOK_DETAIL"],
      flow: "notebook-python"
   },
   {
      slug: "08-chat-with-an-agent",
      title: "Chat with an agent",
      group: "agents",
      order: 8,
      status: "published",
      summary: "Start a conversation and revisit previous sessions.",
      routes: ["PROJECT", "PROJECT_CHAT_SESSIONS", "PROJECT_CHAT_SESSION_DETAIL"],
      flow: "agent-chat"
   },
   {
      slug: "09-ground-an-agent-in-knowledge",
      title: "Ground an agent in knowledge",
      group: "agents",
      order: 9,
      status: "published",
      summary:
         "Curate the business concepts agents cite, and review their proposals.",
      routes: ["PROJECT_KNOWLEDGE", "PROJECT_KNOWLEDGE_DETAIL"],
      flow: "knowledge"
   },
   {
      slug: "10-connect-a-model-provider",
      title: "Connect a model provider",
      group: "agents",
      order: 10,
      status: "published",
      summary: "Add a local or cloud model and choose the default.",
      routes: ["USER_MODEL_CONNECTIONS"],
      flow: "model-provider"
   },
   {
      slug: "11-account",
      title: "Account",
      group: "workspace",
      order: 11,
      status: "published",
      summary: "Review and edit the local profile that owns this workspace.",
      routes: ["ACCOUNT_SETTINGS"],
      flow: "account-settings"
   },
   {
      slug: "12-python-environment",
      title: "Python environment",
      group: "workspace",
      order: 12,
      status: "published",
      summary:
         "Inspect the runtime that executes notebook and chat Python blocks, and prepare it.",
      routes: ["USER_PYTHON_ENVIRONMENT"],
      flow: "account-settings"
   },
   {
      slug: "13-project-settings",
      title: "Project settings",
      group: "workspace",
      order: 13,
      status: "published",
      summary: "Edit the project name and description, and understand local access.",
      routes: ["PROJECT_SETTINGS"],
      flow: "account-settings"
   },
   {
      slug: "14-jobs",
      title: "Jobs and run details",
      group: "workspace",
      order: 14,
      status: "published",
      summary: "Monitor background runs and inspect their parameters, logs, and timing.",
      routes: ["PROJECT_JOBS"],
      flow: "account-settings"
   }
];
