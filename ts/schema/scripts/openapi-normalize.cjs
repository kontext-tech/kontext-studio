/**
 * Shared OpenAPI normalization helpers used by schema export and SDK spec fetches.
 *
 * Keep generator compatibility policy here instead of scattering one-off fixes
 * through the fetch and export scripts.
 */

function isObject(value) {
   return typeof value === "object" && value !== null && !Array.isArray(value);
}

function visit(value, visitor) {
   const replacement = visitor(value);
   const current = replacement === undefined ? value : replacement;

   if (Array.isArray(current)) {
      return current.map((item) => visit(item, visitor));
   }

   if (isObject(current)) {
      for (const [key, child] of Object.entries(current)) {
         current[key] = visit(child, visitor);
      }
   }

   return current;
}

function transformAnyOfNullable(value) {
   return visit(value, (node) => {
      if (
         !isObject(node) ||
         !Array.isArray(node.anyOf) ||
         node.anyOf.length !== 2
      ) {
         return undefined;
      }

      const nullIndex = node.anyOf.findIndex(
         (item) => isObject(item) && item.type === "null"
      );

      if (nullIndex === -1) {
         return undefined;
      }

      const otherSchema = node.anyOf[nullIndex === 0 ? 1 : 0];
      const { anyOf, ...rest } = node;

      if (isObject(otherSchema) && otherSchema.$ref) {
         return {
            ...rest,
            allOf: [{ $ref: otherSchema.$ref }],
            nullable: true
         };
      }

      return {
         ...rest,
         ...otherSchema,
         nullable: true
      };
   });
}

function transformContentMediaTypeBinary(value) {
   return visit(value, (node) => {
      if (
         !isObject(node) ||
         node.type !== "string" ||
         node.contentMediaType !== "application/octet-stream"
      ) {
         return undefined;
      }

      const { contentMediaType, ...rest } = node;
      return {
         ...rest,
         format: "binary"
      };
   });
}

function fixRefsToComponents(value) {
   return visit(value, (node) => {
      if (!isObject(node) || typeof node.$ref !== "string") {
         return undefined;
      }

      if (node.$ref.startsWith("#/") || node.$ref.includes("://")) {
         return undefined;
      }

      return {
         ...node,
         $ref: `#/components/schemas/${node.$ref}`
      };
   });
}

function stripTopLevelSchemaIds(schemas) {
   for (const schema of Object.values(schemas)) {
      if (!isObject(schema)) {
         continue;
      }

      delete schema.id;
      delete schema.$id;
   }
}

function collapseTrivialAllOfRefs(value) {
   return visit(value, (node) => {
      if (
         !isObject(node) ||
         !Array.isArray(node.allOf) ||
         node.allOf.length !== 1 ||
         !isObject(node.allOf[0]) ||
         typeof node.allOf[0].$ref !== "string" ||
         Object.keys(node.allOf[0]).length !== 1 ||
         node.oneOf !== undefined ||
         node.anyOf !== undefined ||
         Object.keys(node).length !== 1
      ) {
         return undefined;
      }

      return { $ref: node.allOf[0].$ref };
   });
}

function normalizeAdditionalProperties(
   schemas,
   { openValueSchema = { type: "object" } } = {}
) {
   for (const schema of Object.values(schemas)) {
      if (!isObject(schema)) {
         continue;
      }

      if (
         schema.type === "object" &&
         !schema.oneOf &&
         !schema.anyOf &&
         !schema.allOf
      ) {
         if (schema.additionalProperties === undefined) {
            schema.additionalProperties = false;
         } else if (
            schema.additionalProperties === true ||
            (isObject(schema.additionalProperties) &&
               Object.keys(schema.additionalProperties).length === 0)
         ) {
            schema.additionalProperties = openValueSchema;
         }
      }

      if (!isObject(schema.properties)) {
         continue;
      }

      for (const prop of Object.values(schema.properties)) {
         if (
            isObject(prop) &&
            prop.type === "object" &&
            isObject(prop.additionalProperties) &&
            Object.keys(prop.additionalProperties).length === 0
         ) {
            prop.additionalProperties = openValueSchema;
         }
      }
   }
}

function stripNumericRanges(value) {
   return visit(value, (node) => {
      if (!isObject(node)) {
         return undefined;
      }

      delete node.minimum;
      delete node.maximum;
      return undefined;
   });
}

function parseComponentRef(ref) {
   if (typeof ref !== "string" || !ref.startsWith("#/components/")) {
      return null;
   }

   const parts = ref.split("/");
   if (parts.length < 4) {
      return null;
   }

   const [, , componentType, componentName] = parts;
   if (!componentType || !componentName) {
      return null;
   }

   return {
      componentType,
      componentName
   };
}

function collectComponentRefs(value, refs = new Set()) {
   visit(value, (node) => {
      if (!isObject(node) || typeof node.$ref !== "string") {
         return undefined;
      }

      const parsed = parseComponentRef(node.$ref);
      if (parsed) {
         refs.add(`${parsed.componentType}:${parsed.componentName}`);
      }

      return undefined;
   });

   return refs;
}

function collectSecuritySchemeRefs(value, refs = new Set()) {
   visit(value, (node) => {
      if (!Array.isArray(node)) {
         return undefined;
      }

      for (const item of node) {
         if (!isObject(item)) {
            continue;
         }

         const entries = Object.entries(item);
         if (
            entries.length === 0 ||
            !entries.every(([, scopes]) => Array.isArray(scopes))
         ) {
            continue;
         }

         for (const [schemeName] of entries) {
            refs.add(`securitySchemes:${schemeName}`);
         }
      }

      return undefined;
   });

   return refs;
}

function pruneUnusedComponents(document) {
   if (!isObject(document) || !isObject(document.components)) {
      return document;
   }

   const referenceableComponentTypes = [
      "schemas",
      "responses",
      "parameters",
      "examples",
      "requestBodies",
      "headers",
      "securitySchemes",
      "links",
      "callbacks",
      "pathItems"
   ];

   const reachable = new Set();
   const queue = [];
   const rootDocument = { ...document };
   delete rootDocument.components;

   for (const ref of collectComponentRefs(rootDocument)) {
      queue.push(ref);
   }

   for (const ref of collectSecuritySchemeRefs(rootDocument)) {
      queue.push(ref);
   }

   while (queue.length > 0) {
      const ref = queue.pop();
      if (!ref || reachable.has(ref)) {
         continue;
      }

      reachable.add(ref);

      const [componentType, componentName] = ref.split(":");
      const componentValue =
         document.components?.[componentType]?.[componentName];
      if (!componentValue) {
         continue;
      }

      for (const nestedRef of collectComponentRefs(componentValue)) {
         if (!reachable.has(nestedRef)) {
            queue.push(nestedRef);
         }
      }
   }

   for (const componentType of referenceableComponentTypes) {
      const entries = document.components?.[componentType];
      if (!isObject(entries)) {
         continue;
      }

      for (const componentName of Object.keys(entries)) {
         const refKey = `${componentType}:${componentName}`;
         if (!reachable.has(refKey)) {
            delete entries[componentName];
         }
      }

      if (Object.keys(entries).length === 0) {
         delete document.components[componentType];
      }
   }

   if (Object.keys(document.components).length === 0) {
      delete document.components;
   }

   return document;
}

function normalizeSchemaComponents(schemas, options = {}) {
   const normalized = schemas;

   if (options.anyOfNullable) {
      transformAnyOfNullable(normalized);
   }

   if (options.binaryContentMediaTypes) {
      transformContentMediaTypeBinary(normalized);
   }

   if (options.componentRefs) {
      fixRefsToComponents(normalized);
   }

   if (options.stripTopLevelIds) {
      stripTopLevelSchemaIds(normalized);
   }

   if (options.stripNumericRanges) {
      stripNumericRanges(normalized);
   }

   if (options.normalizeAdditionalProperties) {
      normalizeAdditionalProperties(normalized, {
         openValueSchema: options.openAdditionalPropertiesSchema ?? {
            type: "object"
         }
      });
   }

   if (options.collapseTrivialAllOfRefs) {
      collapseTrivialAllOfRefs(normalized);
   }

   return normalized;
}

/**
 * Inline multipart form-data body components at their `$ref` sites.
 *
 * FastAPI emits a named component for every multipart body (`Body_UploadFile`)
 * and points the operation's requestBody at it. SDK generators do not model
 * multipart bodies as classes — they flatten them into operation parameters — so
 * those components have no generated counterpart and are pruned. Inlining them
 * removes the FastAPI-specific component names from the spec and keeps the
 * API spec a subset of the canonical models spec.
 *
 * Because the components disappear, the inlined schema keeps the canonical
 * request body name as its `title`. That documents the body as `UploadFileBody`
 * (the name it has in the canonical models spec) rather than leaving the
 * FastAPI-generated `Body_UploadFile` artifact behind.
 */
function inlineMultipartBodyComponents(document, bodyComponentMap) {
   const entries = Object.entries(bodyComponentMap ?? {});
   if (entries.length === 0) {
      return document;
   }

   const canonicalTitleByComponent = new Map(entries);
   const componentNames = new Set(canonicalTitleByComponent.keys());

   const schemas = document.components?.schemas;
   if (!schemas) {
      return document;
   }

   // Replace `{ $ref: "#/components/schemas/Body_X" }` with the schema itself,
   // retitled to the canonical request model name.
   function inline(node) {
      if (!isObject(node)) {
         return node;
      }

      if (
         typeof node.$ref === "string" &&
         node.$ref.startsWith("#/components/schemas/")
      ) {
         const referenced = node.$ref.slice("#/components/schemas/".length);
         if (componentNames.has(referenced) && isObject(schemas[referenced])) {
            return inline({
               ...schemas[referenced],
               title: canonicalTitleByComponent.get(referenced)
            });
         }
      }

      const result = {};
      for (const [key, value] of Object.entries(node)) {
         if (Array.isArray(value)) {
            result[key] = value.map((item) => inline(item));
         } else if (isObject(value)) {
            result[key] = inline(value);
         } else {
            result[key] = value;
         }
      }
      return result;
   }

   const inlinedPaths = inline(document.paths);
   document.paths = inlinedPaths;

   for (const name of componentNames) {
      delete schemas[name];
   }

   return document;
}

function normalizeOpenApiDocument(document, options = {}) {
   let normalized = document;

   if (options.anyOfNullable) {
      normalized = transformAnyOfNullable(normalized);
   }

   if (options.binaryContentMediaTypes) {
      normalized = transformContentMediaTypeBinary(normalized);
   }

   if (normalized.components?.schemas) {
      normalizeSchemaComponents(normalized.components.schemas, options);
   }

   if (options.inlineMultipartBodyComponents) {
      normalized = inlineMultipartBodyComponents(
         normalized,
         options.inlineMultipartBodyComponents
      );
   }

   if (options.pruneUnusedComponents) {
      pruneUnusedComponents(normalized);
   }

   return normalized;
}

module.exports = {
   collapseTrivialAllOfRefs,
   fixRefsToComponents,
   inlineMultipartBodyComponents,
   normalizeOpenApiDocument,
   normalizeSchemaComponents,
   pruneUnusedComponents,
   stripNumericRanges,
   stripTopLevelSchemaIds,
   transformAnyOfNullable,
   transformContentMediaTypeBinary
};
