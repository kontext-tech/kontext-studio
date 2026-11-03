import {
   defineConfig,
   loadEnv,
   mergeConfig,
   type PluginOption,
   type UserConfig
} from "vite";

export interface FrontendViteContext {
   env: Record<string, string>;
   envConfig: Record<string, string | boolean>;
   isProd: boolean;
   mode: string;
   shouldAnalyze: boolean;
}

interface CreateFrontendViteConfigOptions {
   defaultPort: number;
   envDefaults: Record<string, string | boolean>;
   /**
    * Path to the tsconfig whose `compilerOptions.paths` Vite should honor when
    * resolving imports (Vite 8's native `resolve.tsconfigPaths`). This lets
    * workspace packages resolve from `src` during dev instead of their built
    * `dist`, so edits hot-reload without a rebuild. Relative to the project
    * root.
    */
   tsconfig?: string;
   extendConfig?: (context: FrontendViteContext) => UserConfig;
}

const coerceEnvValue = (
   rawValue: string | undefined,
   defaultValue: string | boolean
): string | boolean => {
   if (rawValue === undefined) {
      return defaultValue;
   }

   if (typeof defaultValue !== "boolean") {
      return rawValue;
   }

   const normalizedValue = rawValue.trim().toLowerCase();

   if (["true", "1", "yes", "on"].includes(normalizedValue)) {
      return true;
   }

   if (["false", "0", "no", "off", ""].includes(normalizedValue)) {
      return false;
   }

   return defaultValue;
};

const createEnvConfigPlugin = (
   envConfig: Record<string, string | boolean>
): PluginOption => ({
   name: "inject-env-config",
   transformIndexHtml(html: string): string {
      const configScript = `<script>\n      window.ENV = ${JSON.stringify(envConfig)};\n      </script>`;

      return html.replace(
         "<!-- VITE_ENV_CONFIG_INJECTION_POINT -->",
         configScript
      );
   }
});

const resolvePort = (
   env: Record<string, string>,
   defaultPort: number
): number => {
   const port = process.env.VITE_PORT || env.VITE_PORT;
   return port ? Number(port) : defaultPort;
};

const resolveEnvConfig = (
   env: Record<string, string>,
   envDefaults: Record<string, string | boolean>
): Record<string, string | boolean> => {
   return Object.fromEntries(
      Object.entries(envDefaults).map(([key, defaultValue]) => [
         key,
         coerceEnvValue(process.env[key] ?? env[key], defaultValue)
      ])
   );
};

export const createFrontendViteConfig = ({
   defaultPort,
   envDefaults,
   tsconfig,
   extendConfig
}: CreateFrontendViteConfigOptions) => {
   return defineConfig(({ mode }) => {
      const env = loadEnv(mode, process.cwd(), "");
      const isProd = mode === "production";
      const shouldAnalyze = process.env.ANALYZE === "true";
      const envConfig = resolveEnvConfig(env, envDefaults);

      const baseConfig: UserConfig = {
         tsconfig,
         plugins: [createEnvConfigPlugin(envConfig)].filter(
            Boolean
         ) as PluginOption[],
         resolve: {
            tsconfigPaths: Boolean(tsconfig),
            // CodeMirror breaks with "Unrecognized extension value in
            // extension set" when its core packages resolve to more than one
            // copy (instanceof checks fail). This is backed by the exact-version
            // pnpm overrides in pnpm-workspace.yaml; dedupe here so the dev
            // server and build also collapse any duplicate that slips through
            // prebundled workspace packages.
            dedupe: [
               "@codemirror/state",
               "@codemirror/view",
               "@codemirror/language",
               "@lezer/common",
               "@lezer/highlight"
            ]
         },
         server: {
            port: resolvePort(env, defaultPort)
         },
         build: {
            outDir: "dist"
         },
         preview: {
            port: resolvePort(env, defaultPort),
            open: false
         }
      };

      const extendedConfig = extendConfig?.({
         env,
         envConfig,
         isProd,
         mode,
         shouldAnalyze
      });

      return mergeConfig(baseConfig, extendedConfig ?? {});
   });
};
