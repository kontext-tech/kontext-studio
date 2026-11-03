import react from "@vitejs/plugin-react-swc";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
   plugins: [react()],
   resolve: {
      // Keep CodeMirror core packages on a single copy — multiple copies break
      // `instanceof` checks ("Unrecognized extension value in extension set").
      // Backed by the exact-version pnpm overrides in pnpm-workspace.yaml.
      dedupe: [
         "@codemirror/state",
         "@codemirror/view",
         "@codemirror/language",
         "@lezer/common",
         "@lezer/highlight"
      ],
      alias: {
         "@kontext-labs/notebook": fileURLToPath(
            new URL("../../ts/notebook/src/index.ts", import.meta.url)
         ),
         "@notebook": fileURLToPath(
            new URL("../../ts/notebook/src", import.meta.url)
         ),
         "buffer": "buffer"
      }
   },
   define: {
      "global": "globalThis",
      "process.env": {},
      "process": { env: {} }
   },
   optimizeDeps: {
      include: ["buffer"]
   },
   server: {
      port: 3000,
      open: true
   },
   build: {
      outDir: "dist",
      sourcemap: true
   }
});
