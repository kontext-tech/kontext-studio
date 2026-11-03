const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { normalizeOpenApiDocument } = require("./openapi-normalize.cjs");

const PROJECT_ROOT = path.resolve(__dirname, "../../..");
const OUTPUT_PATH =
   process.env.KONTEXT_API_SCHEMA_OUT_FILE ||
   path.resolve(__dirname, "../src/schemas/kontext.api.openapi.json");

// FastAPI names multipart body components after the endpoint operation
// (`Body_UploadFile`). SDK generators flatten multipart bodies into operation
// parameters instead of model classes, so these components have no generated
// counterpart and would otherwise make the API spec a superset of the
// canonical models spec. Inline them at their request bodies so the API
// spec stays a strict subset, mapping each generated name to the canonical
// request body declared in ts/schema/src/data-lake/files.ts. The canonical name
// becomes the inlined schema's `title`, so the documented request body reads as
// `UploadFileBody` rather than `Body_UploadFile`.
//
// The mapped names are `*Body`, not `*Request`: the endpoints bind these as flat
// `File()` parameters, so nothing validates incoming uploads against them.
const API_INLINE_BODY_COMPONENTS = {
   Body_UploadFile: "UploadFileBody",
   Body_UploadMultipleFiles: "UploadMultipleFilesBody",
   Body_UpdateFileContent: "UpdateFileContentBody",
   Body_StartChatUploadPreparation: "StartChatUploadPreparationBody",
   Body_ImportOkfBundle: "ImportOkfBundleBody"
};

function loadOfflineApiOpenAPISpec() {
   console.log(
      "🔄 Refreshing Data & AI API OpenAPI spec via offline exporter..."
   );

   const rawSpec = execFileSync(
      "uv",
      [
         "run",
         "--package",
         "kontext-api",
         "python",
         "-m",
         "kontext.api.export_openapi"
      ],
      {
         cwd: PROJECT_ROOT,
         encoding: "utf8",
         env: {
            ...process.env,
            KONTEXT_LOCAL_MODE: "false"
         },
         maxBuffer: 20 * 1024 * 1024
      }
   );

   return JSON.parse(rawSpec);
}

async function fetchApiOpenAPISpec() {
   try {
      let spec = loadOfflineApiOpenAPISpec();

      console.log(
         "🔧 Normalizing Data & AI API OpenAPI spec for SDK compatibility..."
      );
      spec = normalizeOpenApiDocument(spec, {
         anyOfNullable: true,
         binaryContentMediaTypes: true,
         inlineMultipartBodyComponents: API_INLINE_BODY_COMPONENTS,
         normalizeAdditionalProperties: true,
         pruneUnusedComponents: true
      });

      fs.writeFileSync(OUTPUT_PATH, JSON.stringify(spec, null, 2));

      console.log(`✅ Data & AI API OpenAPI spec saved to: ${OUTPUT_PATH}`);
      console.log(
         `📊 Spec contains ${Object.keys(spec.paths || {}).length} paths`
      );
      return spec;
   } catch (error) {
      throw new Error(
         `Failed to export Data & AI API OpenAPI spec offline: ${error.message}`
      );
   }
}

if (require.main === module) {
   fetchApiOpenAPISpec()
      .then(() => {
         console.log(
            "🎉 Data & AI API OpenAPI spec refresh completed successfully!"
         );
         process.exit(0);
      })
      .catch((error) => {
         console.error(
            "❌ Failed to refresh Data & AI API OpenAPI spec:",
            error.message
         );
         console.error(
            "💡 The exporter imports the FastAPI app directly, so no running service is required."
         );
         process.exit(1);
      });
}

module.exports = {
   API_INLINE_BODY_COMPONENTS,
   fetchApiOpenAPISpec,
   loadOfflineApiOpenAPISpec
};
