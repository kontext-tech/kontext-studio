/**
 * Parse `app/src/routing/routes.ts` into a stable route inventory.
 *
 * The route table is the source of truth for documentation coverage, so it is
 * read with the TypeScript compiler API rather than regexes. `routes.ts` cannot
 * be imported directly: it pulls in React, lazy components, and the icon
 * registry, none of which exist in a Node process.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import ts from "typescript";

import { routeTypesSource, routesSource } from "./paths.mjs";

function propertyKey(node) {
   if (ts.isIdentifier(node)) return node.text;
   if (ts.isStringLiteral(node)) return node.text;
   if (ts.isComputedPropertyName(node)) {
      const expression = node.expression;
      if (ts.isPropertyAccessExpression(expression)) {
         return `${expression.expression.getText()}.${expression.name.text}`;
      }
      return expression.getText();
   }
   return node.getText();
}

function literalValue(node) {
   if (node === undefined) return undefined;
   if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text;
   if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
   if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
   return undefined;
}

function symbolNames(node) {
   if (node === undefined || !ts.isArrayLiteralExpression(node)) return [];
   return node.elements
      .map((element) => {
         if (ts.isPropertyAccessExpression(element)) return element.name.text;
         return element.getText();
      })
      .filter(Boolean);
}

function isAlwaysHidden(node) {
   if (node === undefined || !ts.isArrowFunction(node)) return false;
   if (node.parameters.length > 0) return false;
   const body = node.body;
   if (ts.isBlock(body)) {
      const statements = body.statements.filter(
         (statement) => !ts.isReturnStatement(statement)
      );
      if (statements.length > 0) return false;
      const [only] = body.statements;
      return (
         only !== undefined &&
         ts.isReturnStatement(only) &&
         only.expression?.kind === ts.SyntaxKind.FalseKeyword
      );
   }
   return body.kind === ts.SyntaxKind.FalseKeyword;
}

function readRouteNames() {
   const source = fs.readFileSync(routeTypesSource, "utf8");
   const sourceFile = ts.createSourceFile(
      routeTypesSource,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS
   );
   for (const statement of sourceFile.statements) {
      if (!ts.isEnumDeclaration(statement)) continue;
      if (statement.name.text !== "RouteNames") continue;
      return new Set(statement.members.map((member) => propertyKey(member.name)));
   }
   throw new Error(`Could not find the RouteNames enum in ${routeTypesSource}.`);
}

function findRouteConfigObject(sourceFile) {
   for (const statement of sourceFile.statements) {
      if (!ts.isVariableStatement(statement)) continue;
      for (const declaration of statement.declarationList.declarations) {
         if (declaration.name.getText() !== "ROUTE_CONFIG") continue;
         const initializer = declaration.initializer;
         if (initializer && ts.isObjectLiteralExpression(initializer)) {
            return initializer;
         }
      }
   }
   return null;
}

function readRoute(property) {
   const rawKey = propertyKey(property.name);
   const name = rawKey.startsWith("RouteNames.")
      ? rawKey.slice("RouteNames.".length)
      : rawKey;

   if (!property.initializer || !ts.isObjectLiteralExpression(property.initializer)) {
      throw new Error(`Route ${name} does not use an object literal.`);
   }

   const fields = new Map();
   for (const member of property.initializer.properties) {
      if (!ts.isPropertyAssignment(member)) continue;
      fields.set(propertyKey(member.name), member.initializer);
   }

   const pathPattern = literalValue(fields.get("pathPattern"));
   if (typeof pathPattern !== "string") {
      throw new Error(`Route ${name} has no string pathPattern.`);
   }

   const roles = symbolNames(fields.get("allowedSystemRoles"));
   const labelNode = fields.get("label");
   const isPublic = literalValue(fields.get("isPublic"));
   const layoutNode = fields.get("layout");

   return {
      name,
      pathPattern,
      label:
         typeof literalValue(labelNode) === "string"
            ? literalValue(labelNode)
            : null,
      layout: ts.isIdentifier(layoutNode) ? layoutNode.text : null,
      public: isPublic === true,
      hidden: isAlwaysHidden(fields.get("visible")),
      sidebar: fields.has("key"),
      adminOnly: roles.includes("ADMINISTRATOR"),
      permissions: symbolNames(fields.get("allowedPermissionClaims")),
      features: symbolNames(fields.get("requiredFeatures")),
      dynamic: pathPattern.includes(":")
   };
}

export function buildInventory() {
   const source = fs.readFileSync(routesSource, "utf8");
   const sourceFile = ts.createSourceFile(
      routesSource,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TS
   );

   const config = findRouteConfigObject(sourceFile);
   if (!config) {
      throw new Error("Could not find the ROUTE_CONFIG object in routes.ts.");
   }

   const routeNames = readRouteNames();
   const routes = [];
   for (const property of config.properties) {
      if (!ts.isPropertyAssignment(property)) continue;
      const route = readRoute(property);
      if (!routeNames.has(route.name)) {
         throw new Error(
            `Route ${route.name} is in ROUTE_CONFIG but not in the RouteNames enum. ` +
               "Add it to app/src/types/routeTypes.ts."
         );
      }
      routes.push(route);
   }

   if (routes.length !== routeNames.size) {
      const seen = new Set(routes.map((route) => route.name));
      const missing = [...routeNames].filter((name) => !seen.has(name));
      throw new Error(
         `RouteNames and ROUTE_CONFIG disagree; missing from ROUTE_CONFIG: ${missing.join(", ")}`
      );
   }

   return {
      generatedFrom: "app/src/routing/routes.ts",
      sourceHash: crypto.createHash("sha256").update(source).digest("hex"),
      routeCount: routes.length,
      routes
   };
}

export function serializeInventory(inventory) {
   return `${JSON.stringify(inventory, null, 2)}\n`;
}

export function readInventory() {
   return JSON.parse(fs.readFileSync(new URL("../inventory.generated.json", import.meta.url)));
}
