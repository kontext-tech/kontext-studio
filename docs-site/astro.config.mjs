import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

import {
   cleanUserGuideSlug,
   developerPagesByGroup,
   repoUrl,
   userGuidePagesByGroup
} from "./site-manifest.mjs";

// Defaults target the planned custom domain. Set DOCS_SITE_URL/DOCS_BASE when
// hosting under a path (for example a `/docs` prefix) instead of a subdomain.
const site = process.env.DOCS_SITE_URL ?? "https://docs.kontext.tech";
const base = process.env.DOCS_BASE ?? "/";

const userGuideGroupsConfig = userGuidePagesByGroup.map((group) => ({
   label: group.label,
   items: group.pages.map((page) => ({
      label: page.title,
      link: `/user-guide/${cleanUserGuideSlug(page.slug)}/`
   }))
}));

const developerGroupsConfig = developerPagesByGroup.map((group) => ({
   label: group.label,
   collapsed: true,
   items: group.docs.map((doc) => ({
      label: doc.title,
      link: `/${doc.route}/`
   }))
}));

export default defineConfig({
   site,
   base,
   integrations: [
      starlight({
         title: "Kontext Labs Docs",
         description:
            "Kontext Labs documentation: install the local workspace, connect data and model providers, and work with notebooks, agents, and jobs.",
         logo: {
            light: "./src/assets/logo.svg",
            dark: "./src/assets/logo-dark.svg",
            alt: "Kontext Labs Docs",
            replacesTitle: true
         },
         favicon: "/favicon.svg",
         customCss: ["./src/styles/custom.css"],
         components: {
            Footer: "./src/components/SiteFooter.astro"
         },
         expressiveCode: {
            themes: ["github-dark", "github-light"],
            defaultProps: { wrap: true }
         },
         social: [{ icon: "github", label: "GitHub", href: repoUrl }],
         sidebar: [
            { label: "Home", link: "/" },
            {
               label: "User guide",
               items: [
                  { label: "Overview", link: "/user-guide/" },
                  ...userGuideGroupsConfig
               ]
            },
            {
               label: "Developer guide",
               items: [
                  { label: "Overview", link: "/develop/" },
                  ...developerGroupsConfig
               ]
            },
            { label: "Platform docs", link: "https://kontext.tech/docs" }
         ]
      })
   ]
});
