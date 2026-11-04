/**
 * Pages published from `docs/` by the docs site.
 *
 * The user guide is driven by `tools/docs-capture/pages.mjs`. Only durable
 * reference documents belong here: plans, decision records, and roadmaps stay
 * in the repository and are deliberately not published.
 */
import {
   pageGroups,
   pages
} from "../tools/docs-capture/pages.mjs";

export const docsPreview = process.env.DOCS_PREVIEW === "true";

export const repoUrl =
   process.env.DOCS_REPO_URL ?? "https://github.com/kontext-tech/kontext-labs";

export function cleanUserGuideSlug(slug) {
   return slug.replace(/^\d+-/, "");
}

export const publishedUserGuidePages = pages
   .filter((page) => page.status === "published")
   .sort((a, b) => a.order - b.order);

export const userGuidePagesByGroup = pageGroups
   .map((group) => ({
      ...group,
      pages: publishedUserGuidePages.filter((page) => page.group === group.id)
   }))
   .filter((group) => group.pages.length > 0);

export const developerGroups = [
   { id: "ai", label: "AI architecture" },
   { id: "notebook", label: "Notebook" },
   { id: "workflows", label: "Repository workflows" }
];

export const developerDocs = [
   {
      source: "ai/ai-architecture.md",
      route: "develop/ai/ai-architecture",
      title: "AI architecture",
      description:
         "Agents, teams, tools, and the SQL validation path behind Kontext's AI features.",
      group: "ai",
      order: 1
   },
   {
      source: "ai/harness-abstraction.md",
      route: "develop/ai/harness-abstraction",
      title: "Agent harness abstraction",
      description:
         "How the agent framework stays a swappable adapter behind neutral contracts.",
      group: "ai",
      order: 2
   },
   {
      source: "ai/model-provider-configuration.md",
      route: "develop/ai/model-provider-configuration",
      title: "Model provider configuration",
      description:
         "Provider inputs, catalog defaults, and the harness-neutral model object.",
      group: "ai",
      order: 3
   },
   {
      source: "ai/tool-results-schema.md",
      route: "develop/ai/tool-results-schema",
      title: "Tool result schemas",
      description:
         "The shared transport schema for tool results across TypeScript and Python.",
      group: "ai",
      order: 4
   },
   {
      source: "notebook/notebook-system.md",
      route: "develop/notebook/notebook-system",
      title: "Notebook system",
      description:
         "The block document model, package layout, and host integration contract.",
      group: "notebook",
      order: 1
   },
   {
      source: "development/generated-code.md",
      route: "develop/workflows/generated-code",
      title: "Generated code",
      description:
         "The committed API types and Python models, and how to regenerate them.",
      group: "workflows",
      order: 1
   },
   {
      source: "development/openapi-workflow.md",
      route: "develop/workflows/openapi-workflow",
      title: "OpenAPI workflow",
      description:
         "Refreshing and validating the tracked API specifications.",
      group: "workflows",
      order: 2
   },
   {
      source: "development/python-package-boundaries.md",
      route: "develop/workflows/python-package-boundaries",
      title: "Python package boundaries",
      description:
         "The Python package responsibility matrix and dependency rules.",
      group: "workflows",
      order: 3
   },
   {
      source: "development/releasing.md",
      route: "develop/workflows/releasing",
      title: "Releasing",
      description:
         "The app, wheel, TypeScript package, and docs publishing paths.",
      group: "workflows",
      order: 4
   }
];

export const developerPagesByGroup = developerGroups
   .map((group) => ({
      ...group,
      docs: developerDocs
         .filter((doc) => doc.group === group.id)
         .sort((a, b) => a.order - b.order)
   }))
   .filter((group) => group.docs.length > 0);
