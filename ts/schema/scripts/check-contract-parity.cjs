#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const spec = JSON.parse(
   fs.readFileSync(
      path.resolve(__dirname, "../src/schemas/kontext.models.openapi.json"),
      "utf8"
   )
);

const schemas = spec.components.schemas;
const failures = [];

function assert(condition, message) {
   if (!condition) {
      failures.push(message);
   }
}

function hasRef(node, name) {
   return JSON.stringify(node).includes(`"#/components/schemas/${name}"`);
}

function refEquals(node, name) {
   return node?.$ref === `#/components/schemas/${name}`;
}

assert(
   schemas.AccessLevel?.["x-enumValues"],
   "AccessLevel enum metadata missing"
);
assert(
   schemas.AccessLevel?.["x-enum-varnames"],
   "AccessLevel Python enum names missing"
);
assert(
   schemas.ProjectModel?.properties?.id?.format === "uuid",
   "ProjectModel.id must remain uuid-formatted"
);
assert(
   Array.isArray(schemas.NotebookBlock?.oneOf) &&
      hasRef(schemas.NotebookBlock, "ParagraphBlock") &&
      hasRef(schemas.NotebookBlock, "ChartBlock"),
   "NotebookBlock discriminated union references missing"
);
assert(
   schemas.ParagraphBlock?.properties?.type?.default === "paragraph" &&
      refEquals(
         schemas.ParagraphBlock?.properties?.type?.allOf?.[0],
         "NotebookBlockType"
      ),
   "Notebook block discriminator literal missing"
);
assert(
   Array.isArray(schemas.ChartConfig?.oneOf) &&
      hasRef(schemas.ChartConfig, "LineChartConfig") &&
      hasRef(schemas.ChartConfig, "PieChartConfig"),
   "ChartConfig union references missing"
);
assert(
   schemas.ProjectModel?.additionalProperties === false,
   "ProjectModel should be closed by default"
);
assert(
   schemas.PythonExecutionApprovalMode?.enum?.includes("always_ask") &&
      schemas.PythonExecutionApprovalMode?.enum?.includes("auto_approve"),
   "PythonExecutionApprovalMode enum component missing"
);
assert(
   schemas.PythonExecutionTargetType?.enum?.includes("notebook") &&
      schemas.PythonExecutionTargetType?.enum?.includes("session"),
   "PythonExecutionTargetType enum component missing"
);
assert(
   hasRef(
      schemas.ChatSessionModel?.properties?.pythonExecutionApprovalMode,
      "PythonExecutionApprovalMode"
   ),
   "ChatSessionModel.pythonExecutionApprovalMode must reference PythonExecutionApprovalMode"
);
assert(
   hasRef(
      schemas.PythonExecutionResult?.properties?.targetType,
      "PythonExecutionTargetType"
   ),
   "PythonExecutionResult.targetType must reference PythonExecutionTargetType"
);
assert(
   !!schemas.ExecutePythonScriptRequest,
   "ExecutePythonScriptRequest component missing"
);
assert(!!schemas.AttachedDataSource, "AttachedDataSource component missing");
assert(!!schemas.AttachedDataTable, "AttachedDataTable component missing");
assert(
   refEquals(
      schemas.AgentSessionState?.properties?.attachedDataSources?.items,
      "AttachedDataSource"
   ),
   "AgentSessionState.attachedDataSources items must reference AttachedDataSource"
);
assert(
   refEquals(
      schemas.AttachedDataSource?.properties?.tables?.items,
      "AttachedDataTable"
   ),
   "AttachedDataSource.tables items must reference AttachedDataTable"
);
assert(
   !!schemas.ChatAttachmentContextFile,
   "ChatAttachmentContextFile component missing"
);
assert(
   !!schemas.ChatAttachmentContextTable,
   "ChatAttachmentContextTable component missing"
);
assert(
   !!schemas.ChatAttachmentContext,
   "ChatAttachmentContext component missing"
);
assert(
   refEquals(
      schemas.ChatAttachmentContext?.properties?.files?.items,
      "ChatAttachmentContextFile"
   ),
   "ChatAttachmentContext.files items must reference ChatAttachmentContextFile"
);
assert(
   refEquals(
      schemas.ChatAttachmentContext?.properties?.tables?.items,
      "ChatAttachmentContextTable"
   ),
   "ChatAttachmentContext.tables items must reference ChatAttachmentContextTable"
);
assert(
   !!schemas.SeedChatAttachmentContextRequest,
   "SeedChatAttachmentContextRequest component missing"
);
assert(
   !!schemas.ChatUploadPreparationAcceptedFile,
   "ChatUploadPreparationAcceptedFile component missing"
);
assert(
   !!schemas.ChatUploadPreparationFailure,
   "ChatUploadPreparationFailure component missing"
);
assert(
   !!schemas.ChatUploadPreparationStep,
   "ChatUploadPreparationStep component missing"
);
assert(
   !!schemas.ChatUploadPreparationStatus,
   "ChatUploadPreparationStatus component missing"
);
assert(
   !!schemas.StartChatUploadPreparationResponse,
   "StartChatUploadPreparationResponse component missing"
);
assert(
   refEquals(
      schemas.StartChatUploadPreparationResponse?.properties?.acceptedFiles
         ?.items,
      "ChatUploadPreparationAcceptedFile"
   ),
   "StartChatUploadPreparationResponse.acceptedFiles items must reference ChatUploadPreparationAcceptedFile"
);
assert(
   refEquals(
      schemas.StartChatUploadPreparationResponse?.properties?.uploadErrors
         ?.items,
      "ChatUploadPreparationFailure"
   ),
   "StartChatUploadPreparationResponse.uploadErrors items must reference ChatUploadPreparationFailure"
);
assert(
   refEquals(
      schemas.ChatUploadPreparationStatus?.properties?.failedFiles?.items,
      "ChatUploadPreparationFailure"
   ),
   "ChatUploadPreparationStatus.failedFiles items must reference ChatUploadPreparationFailure"
);
assert(
   refEquals(
      schemas.ChatUploadPreparationStatus?.properties?.steps?.items,
      "ChatUploadPreparationStep"
   ),
   "ChatUploadPreparationStatus.steps items must reference ChatUploadPreparationStep"
);

// ---------------------------------------------------------------------------
// Spec-subset invariant
//
// The generated API clients re-export their models from the canonical schema
// package instead of defining duplicates. That only holds while every component
// in the API spec also exists as a component in the comprehensive
// models spec. A API-only component would force the client generators to
// emit a model that has no `@kontext-tech/schema` counterpart.
// ---------------------------------------------------------------------------
const apiSpecPath = path.resolve(
   __dirname,
   "../src/schemas/kontext.api.openapi.json"
);

if (fs.existsSync(apiSpecPath)) {
   const apiSchemas =
      JSON.parse(fs.readFileSync(apiSpecPath, "utf8")).components?.schemas ??
      {};
   const modelsNames = new Set(Object.keys(schemas));
   const apiOnly = Object.keys(apiSchemas).filter(
      (name) => !modelsNames.has(name)
   );

   assert(
      apiOnly.length === 0,
      `API spec has components missing from kontext.models.openapi.json` +
         ` (register them in scripts/export-schemas.mjs):\n` +
         apiOnly.map((name) => `      - ${name}`).join("\n")
   );
}

// ---------------------------------------------------------------------------
// SiteFeature TS <-> Python mirror parity
//
// `SiteFeature` is defined twice by design: as part of the shared Zod models
// (below) and as the server-side StrEnum in
// py/kontext-common/src/kontext/common/constants/site_features.py. The server
// advertises the enabled subset through SiteConfigResponse, so a typo or a
// one-sided edit silently disables (or dead-codes) a feature. This check pins
// the two mirrors to the exact same name -> value mapping.
// ---------------------------------------------------------------------------
const tsSiteFeaturePath = path.resolve(
   __dirname,
   "../src/core/domains/base/index.ts"
);
const pySiteFeaturePath = path.resolve(
   __dirname,
   "../../../py/kontext-common/src/kontext/common/constants/site_features.py"
);

if (fs.existsSync(tsSiteFeaturePath) && fs.existsSync(pySiteFeaturePath)) {
   const tsSource = fs.readFileSync(tsSiteFeaturePath, "utf8");
   const tsBlock = tsSource.match(
      /export const SiteFeature = \{([\s\S]*?)\} as const;/
   );
   const pySource = fs.readFileSync(pySiteFeaturePath, "utf8");
   const pyBlock = pySource.match(
      /class SiteFeature\(StrEnum\):([\s\S]*?)(?:\n[A-Za-z@#]|\n$)/
   );

   assert(tsBlock !== null, "TS SiteFeature const not found in base/index.ts");
   assert(
      pyBlock !== null,
      "Python SiteFeature enum not found in site_features.py"
   );

   if (tsBlock && pyBlock) {
      const tsFeatures = new Map();
      for (const m of tsBlock[1].matchAll(/([A-Z_0-9]+):\s*"([^"]+)"/g)) {
         tsFeatures.set(m[1], m[2]);
      }

      const pyFeatures = new Map();
      for (const m of pyBlock[1].matchAll(/([A-Z_0-9]+)\s*=\s*"([^"]+)"/g)) {
         pyFeatures.set(m[1], m[2]);
      }

      assert(
         pyFeatures.size > 0,
         "No SiteFeature members parsed from Python mirror"
      );

      for (const [name, value] of tsFeatures) {
         assert(
            pyFeatures.has(name),
            `SiteFeature '${name}' exists in TS but is missing from the Python mirror`
         );
         assert(
            pyFeatures.get(name) === value,
            `SiteFeature '${name}' value mismatch: TS '${value}' vs Python '${pyFeatures.get(name)}'`
         );
      }
      for (const name of pyFeatures.keys()) {
         assert(
            tsFeatures.has(name),
            `SiteFeature '${name}' exists in Python but is missing from the TS mirror`
         );
      }
   }
}

if (failures.length > 0) {
   throw new Error(
      `Contract parity checks failed:\n${failures
         .map((failure) => `  - ${failure}`)
         .join("\n")}`
   );
}

console.log("ok representative contract parity checks passed");
