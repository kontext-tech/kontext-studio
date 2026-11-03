import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import path from "path";
import tseslint from "typescript-eslint";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default tseslint.config(
   // Global ignores
   {
      ignores: [
         "**/dist/**",
         "build/**",
         "node_modules/**",
         "coverage/**",
         "**/*.d.ts",
         "docs/**",
         "scripts/**",
         ".git/**",
         ".vscode/**",
         "**/*.config.ts",
         "**/*.config.js",
         "**/*.config.mjs",
         "py/**",
         // Generated API types - owned by openapi-typescript
         "ts/schema/src/generated/**",
         "ts/schema/scripts/**",
         // App build output
         "app/dist/**"
      ]
   },

   // Base configuration for all TypeScript files
   {
      extends: [js.configs.recommended, ...tseslint.configs.recommended],
      files: ["**/*.{ts,tsx}"],
      languageOptions: {
         ecmaVersion: 2020,
         globals: globals.browser,
         parserOptions: {
            tsconfigRootDir: __dirname
         }
      },
      rules: {
         "@typescript-eslint/no-explicit-any": "error",
         "@typescript-eslint/no-unused-vars": [
            "warn",
            {
               argsIgnorePattern: "^_",
               varsIgnorePattern: "^_"
            }
         ],
         "prefer-const": "error",
         "no-var": "error",
         // F9.13 (D-B): informational console noise is stripped from prod
         // bundles; diagnostics belong in @kontext-labs/common `logger` —
         // demo code under examples/ is exempt above.
         "no-console": [
            "error",
            {
               allow: ["warn", "error"]
            }
         ]
      }
   },

   {
      // Notebook demo/mock code is standalone demo material where console
      // output is a documented feature of the mock services; the no-console
      // ratchet (below) applies to production packages and the app only.
      files: ["examples/**/*.{ts,tsx}"],
      rules: {
         "no-console": "off"
      }
   },
   {
      files: ["ts/**/*.{ts,tsx}"],
      rules: {
         "no-restricted-imports": [
            "error",
            {
               patterns: [
                  {
                     group: ["@/**"],
                     message:
                        "Shared packages must not import app-local modules via the @/ alias."
                  },
                  {
                     group: ["app", "app/*"],
                     message: "Shared packages must not import from app modules."
                  },
                  {
                     group: ["@kontext-labs/*/src", "@kontext-labs/*/src/*"],
                     message:
                        "Import packages through their public entry points, not src internals."
                  }
               ]
            }
         ]
      }
   },

   // React-specific configuration for apps and shared React packages
   {
      files: [
         "app/**/*.{ts,tsx}",
         "ts/notebook/**/*.{ts,tsx}",
         "ts/common/**/*.{ts,tsx}",
         "ts/account/**/*.{ts,tsx}",
         "ts/auth/**/*.{ts,tsx}",
         "ts/chat/**/*.{ts,tsx}",
         "ts/event/**/*.{ts,tsx}",
         "ts/file/**/*.{ts,tsx}",
         "ts/job/**/*.{ts,tsx}",
         "ts/layout/**/*.{ts,tsx}",
         "ts/query/**/*.{ts,tsx}",
         "ts/app-runtime/**/*.{ts,tsx}",
         "ts/theme/**/*.{ts,tsx}",
         "ts/ui/**/*.{ts,tsx}"
      ],
      languageOptions: {
         globals: globals.browser,
         parserOptions: {
            tsconfigRootDir: __dirname
         }
      },
      plugins: {
         "react-hooks": reactHooks
      },
      rules: {
         ...reactHooks.configs.recommended.rules,
         "no-restricted-imports": [
            "error",
            {
               patterns: [
                  {
                     group: ["@icons", "@icons/*", "@antd", "@antd/*"],
                     message:
                        "Use the shared @/ source alias instead of legacy local aliases."
                  }
               ]
            }
         ]
      }
   },

   // Fast refresh warnings only make sense for live app surfaces
   {
      files: ["app/**/*.{ts,tsx}"],
      languageOptions: {
         globals: globals.browser,
         parserOptions: {
            tsconfigRootDir: __dirname
         }
      },
      plugins: {
         "react-refresh": reactRefresh
      },
      rules: {
         "react-refresh/only-export-components": [
            "warn",
            { allowConstantExport: true }
         ]
      }
   },

   // Node.js specific configuration for repo tooling and sample apps
   {
      files: ["tools/**/*.{ts,tsx}", "examples/**/*.{ts,tsx}"],
      languageOptions: {
         globals: {
            ...globals.node,
            ...globals.browser
         },
         parserOptions: {
            tsconfigRootDir: __dirname
         }
      }
   }
);
