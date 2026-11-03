import { createFrontendViteConfig } from "@kontext-labs/build-config/vite";
import path from "node:path";
import { visualizer } from "rollup-plugin-visualizer";
import { compression } from "vite-plugin-compression2";
import svgr from "vite-plugin-svgr";

// Production bundles are minified (terser) only. Do not add obfuscation:
// the app source ships under the repository MIT license, so obfuscating the
// output protects nothing while inflating size and build time.

export default createFrontendViteConfig({
   defaultPort: 8002,
   // Resolve every `@kontext-labs/*` workspace import from its `src` (via the
   // paths in tsconfig.app.json) so editing a shared package hot-reloads
   // without running `build:shared`. The few packages whose tsconfig path
   // targets built output are aliased to source below. `@kontext-labs/build-config`
   // is loaded by the Vite config itself and stays on its built output.
   tsconfig: "./tsconfig.app.json",
   envDefaults: {
      PUBLIC_KONTEXT_API_URL: "http://localhost:8101",
      PUBLIC_KONTEXT_DATA_API_URL: "http://localhost:8000",
      PUBLIC_KONTEXT_URL: "http://localhost:8006",
      PUBLIC_KONTEXT_APP_URL: "http://localhost:8002",
      KONTEXT_LOCAL_MODE: "false",
      IS_DEVELOPMENT: true,
      VERSION: "development"
   },
   extendConfig: ({ isProd, shouldAnalyze }) => ({
      worker: {
         format: "es"
      },
      resolve: {
         alias: [
            {
               find: /^@\//,
               replacement: `${path.resolve(import.meta.dirname, "./src")}/`
            },
            // The tsconfig path for schema points at its built `dist` (so
            // `tsc --build` never type-checks generated sources under the
            // app's strict flags). Alias it to `src` here so the dev server
            // still hot-reloads edits without a rebuild.
            {
               find: /^@kontext-labs\/schema$/,
               replacement: path.resolve(
                  import.meta.dirname,
                  "../ts/schema/src/index.ts"
               )
            },
            // Notebook resolves from source too so it hot-reloads. It uses its
            // own internal `@notebook/*` alias, which the app tsconfig paths do
            // not expose. `verbatimModuleSyntax` is enabled for every library
            // package, so its source is safe for esbuild to consume directly.
            {
               find: /^@kontext-labs\/notebook$/,
               replacement: path.resolve(
                  import.meta.dirname,
                  "../ts/notebook/src/index.ts"
               )
            },
            {
               find: /^@notebook\//,
               replacement: `${path.resolve(import.meta.dirname, "../ts/notebook/src")}/`
            }
         ],
         dedupe: ["react", "react-dom"]
      },
      plugins: [
         svgr({
            include: "**/*.svg?react"
         }),
         isProd &&
            compression({
               algorithms: ["gzip"],
               threshold: 1024,
               deleteOriginalAssets: false
            }),
         isProd && {
            name: "inject-preconnect",
            transformIndexHtml(html: string): string {
               return html.replace(
                  "<!-- VITE_PRECONNECT_INJECTION_POINT -->",
                  `<link rel="dns-prefetch" href="//api.kontext.tech" />
      <link rel="preconnect" href="https://api.kontext.tech" crossorigin />`
               );
            }
         },
         shouldAnalyze &&
            visualizer({
               open: true,
               filename: "dist/stats.html",
               gzipSize: true,
               brotliSize: true
            })
      ],
      server: {
         cors: {
            origin: ["http://localhost:8006"],
            credentials: true,
            methods: ["GET", "HEAD", "PUT", "PATCH", "POST", "DELETE"],
            allowedHeaders: ["Content-Type", "Authorization"]
         },
         proxy: {
            "/robots.txt": {
               target:
                  process.env.services__api__https__0 ||
                  process.env.services__api__http__0 ||
                  "http://localhost:8101",
               changeOrigin: true,
               secure: false
            },
            "/sitemap": {
               target:
                  process.env.services__api__https__0 ||
                  process.env.services__api__http__0 ||
                  "http://localhost:8101",
               changeOrigin: true,
               secure: false
            }
         },
         hmr: {
            overlay: true,
            preserveState: true
         }
      },
      build: {
         chunkSizeWarningLimit: 500,
         sourcemap: false,
         cssCodeSplit: true,
         minify: "terser",
         terserOptions: {
            compress: {
               // Keep console.warn/error in production bundles so shipped app
               // failures remain diagnosable; pure_funcs below removes the
               // informational noise. (drop_console removed more than needed.)
               drop_console: false,
               drop_debugger: true,
               pure_funcs: ["console.log", "console.info", "console.debug"]
            }
         },
         rolldownOptions: {
            input: "./index.html",
            // React libraries ship a `"use client"` directive for React Server
            // Components. This app is a client-only SPA (no RSC runtime), so
            // the directive's semantics are irrelevant and Rolldown's warning
            // for every such dependency is pure noise. Terser minification
            // always dominates build time, so the timing report adds nothing
            // either; profile with `node --cpu-prof` when actually needed.
            checks: {
               moduleLevelDirective: false,
               bundlerTimings: false
            },
            output: {
               chunkFileNames:
                  isProd && !shouldAnalyze
                     ? "assets/[hash].js"
                     : "assets/[name]-[hash].js",
               entryFileNames:
                  isProd && !shouldAnalyze
                     ? "assets/[hash].js"
                     : "assets/[name]-[hash].js",
               assetFileNames:
                  isProd && !shouldAnalyze
                     ? "assets/[hash].[ext]"
                     : "assets/[name]-[hash].[ext]",
               manualChunks(id) {
                  // mermaid must come before antd-x since @ant-design/x depends on it
                  if (id.includes("node_modules/mermaid")) {
                     return "vendor-mermaid";
                  }
                  // react-syntax-highlighter must come before antd-x
                  if (id.includes("node_modules/react-syntax-highlighter")) {
                     return "vendor-syntax-highlighter";
                  }
                  if (
                     id.includes("node_modules/@codemirror") ||
                     id.includes("node_modules/@uiw/react-codemirror") ||
                     id.includes("node_modules/@lezer")
                  ) {
                     return "vendor-codemirror";
                  }
                  if (id.includes("node_modules/@editorjs")) {
                     return "vendor-editorjs";
                  }
                  if (id.includes("node_modules/@ant-design/x")) {
                     return "vendor-antd-x";
                  }
                  if (
                     id.includes("node_modules/antd") ||
                     id.includes("node_modules/@ant-design/icons") ||
                     id.includes("node_modules/rc-")
                  ) {
                     return "vendor-antd";
                  }
                  if (
                     id.includes("node_modules/react-dom") ||
                     id.includes("node_modules/react-router") ||
                     id.includes("node_modules/react/")
                  ) {
                     return "vendor-react";
                  }
               }
            }
         }
      }
   })
});
