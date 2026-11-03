#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const schemaDir = path.resolve(__dirname, "../src/schemas");
const specs = [
   "kontext.models.openapi.json",
   "kontext.api.core.openapi.json",
   "kontext.api.openapi.json"
];

function readSpec(fileName) {
   const filePath = path.join(schemaDir, fileName);
   return {
      fileName,
      filePath,
      spec: JSON.parse(fs.readFileSync(filePath, "utf8"))
   };
}

function visit(value, visitor, pointer = "#") {
   visitor(value, pointer);

   if (Array.isArray(value)) {
      value.forEach((item, index) =>
         visit(item, visitor, `${pointer}/${index}`)
      );
      return;
   }

   if (value && typeof value === "object") {
      for (const [key, child] of Object.entries(value)) {
         visit(child, visitor, `${pointer}/${key}`);
      }
   }
}

function validateRef(spec, ref, errors, pointer) {
   if (!ref.startsWith("#/components/schemas/")) {
      return;
   }

   const name = ref.slice("#/components/schemas/".length);
   if (!spec.components?.schemas?.[name]) {
      errors.push(`${pointer}: unresolved component ref ${ref}`);
   }
}

function validateSpec({ fileName, spec }) {
   const errors = [];

   if (!/^3\.(0|1)\.\d+$/.test(spec.openapi || "")) {
      errors.push(`openapi must be 3.0.x or 3.1.x, got ${spec.openapi}`);
   }

   if (!spec.info?.title || !spec.info?.version) {
      errors.push("info.title and info.version are required");
   }

   if (!spec.paths || typeof spec.paths !== "object") {
      errors.push("paths object is required");
   }

   if (
      !spec.components?.schemas ||
      typeof spec.components.schemas !== "object"
   ) {
      errors.push("components.schemas object is required");
   }

   visit(spec, (node, pointer) => {
      if (!node || typeof node !== "object") {
         return;
      }

      if (typeof node.$ref === "string") {
         validateRef(spec, node.$ref, errors, pointer);
      }

      if (Array.isArray(node.type) && node.type.includes("null")) {
         errors.push(
            `${pointer}: generator-facing specs must not use type arrays with null`
         );
      }

      if (
         Array.isArray(node.anyOf) &&
         node.anyOf.some((item) => item && item.type === "null")
      ) {
         errors.push(
            `${pointer}: nullable anyOf null pattern should be normalized before codegen`
         );
      }

      if (
         node.contentMediaType === "application/octet-stream" &&
         node.type === "string"
      ) {
         errors.push(`${pointer}: binary strings should use format: binary`);
      }
   });

   if (errors.length > 0) {
      throw new Error(
         `${fileName}\n${errors.map((e) => `  - ${e}`).join("\n")}`
      );
   }
}

for (const specInfo of specs.map(readSpec)) {
   validateSpec(specInfo);
   console.log(`ok ${specInfo.fileName}`);
}
