/**
 * Tests for the canonical multipart request bodies.
 *
 * FastAPI derives a multipart body from an endpoint's flat `File()` parameters
 * and emits an anonymous `Body_<OperationId>` component for it. These schemas
 * give those bodies stable, canonical names (`*Body`, not `*Request`: nothing
 * validates request payloads against them) so neither the generated spec nor the
 * SDKs expose the FastAPI artifact.
 */

import fs from "node:fs";
import path from "node:path";

import {
   ImportOkfBundleBodySchema,
   StartChatUploadPreparationBodySchema,
   UpdateFileContentBodySchema,
   UploadFileBodySchema,
   UploadMultipleFilesBodySchema
} from "../data-lake/files";

const API_SPEC_PATH = path.resolve(
   __dirname,
   "../schemas/kontext.api.openapi.json"
);

interface RequestBodyContent {
   schema?: { title?: string };
}

interface ApiSpec {
   paths: Record<
      string,
      Record<
         string,
         { requestBody?: { content?: Record<string, RequestBodyContent> } }
      >
   >;
}

/** The multipart endpoints and the canonical body name each must document. */
const MULTIPART_ENDPOINTS: Array<[string, string, string]> = [
   ["/file/upload", "post", "UploadFileBody"],
   ["/file/upload-multiple", "post", "UploadMultipleFilesBody"],
   ["/file/{fileId}/upload", "put", "UpdateFileContentBody"],
   ["/ai/chat/upload-preparations", "post", "StartChatUploadPreparationBody"],
   ["/catalog/okf/import", "post", "ImportOkfBundleBody"]
];

describe("Multipart request bodies", () => {
   describe("UploadFileBody", () => {
      it("accepts a file field", () => {
         expect(UploadFileBodySchema.parse({ file: "data" })).toEqual({
            file: "data"
         });
      });

      it("requires the file field", () => {
         expect(() => UploadFileBodySchema.parse({})).toThrow();
      });
   });

   describe("UploadMultipleFilesBody", () => {
      it("accepts one or more files", () => {
         expect(
            UploadMultipleFilesBodySchema.parse({ files: ["a", "b"] })
         ).toEqual({ files: ["a", "b"] });
      });

      it("rejects an empty file list", () => {
         expect(() =>
            UploadMultipleFilesBodySchema.parse({ files: [] })
         ).toThrow();
      });
   });

   describe("UpdateFileContentBody", () => {
      it("accepts a file field", () => {
         expect(UpdateFileContentBodySchema.parse({ file: "x" })).toEqual({
            file: "x"
         });
      });
   });

   describe("StartChatUploadPreparationBody", () => {
      it("accepts one or more files", () => {
         expect(
            StartChatUploadPreparationBodySchema.parse({ files: ["a"] })
         ).toEqual({ files: ["a"] });
      });

      it("rejects an empty file list", () => {
         expect(() =>
            StartChatUploadPreparationBodySchema.parse({ files: [] })
         ).toThrow();
      });
   });

   describe("ImportOkfBundleBody", () => {
      it("accepts a file field", () => {
         expect(ImportOkfBundleBodySchema.parse({ file: "b" })).toEqual({
            file: "b"
         });
      });
   });

   describe("API spec", () => {
      const spec = JSON.parse(
         fs.readFileSync(API_SPEC_PATH, "utf8")
      ) as ApiSpec;

      /**
       * The canonical names above are only reachable because
       * `API_INLINE_BODY_COMPONENTS` retitles FastAPI's `Body_*` components
       * at their request bodies. Assert the linkage so the map cannot silently
       * drift away from the declared schemas.
       */
      it.each(MULTIPART_ENDPOINTS)(
         "documents %s %s with the canonical body title",
         (pathname, method, expectedTitle) => {
            const operation = spec.paths[pathname]?.[method];
            expect(operation).toBeDefined();

            const schema =
               operation?.requestBody?.content?.["multipart/form-data"]?.schema;
            expect(schema?.title).toBe(expectedTitle);
         }
      );

      /**
       * A body sent as multipart is what makes these upload endpoints work. If a
       * future refactor moved them to a Pydantic form model, FastAPI would emit
       * `application/x-www-form-urlencoded` instead and binary uploads would
       * break. Pin the media type.
       */
      it.each(MULTIPART_ENDPOINTS)(
         "keeps %s %s on multipart/form-data",
         (pathname, method) => {
            const content =
               spec.paths[pathname]?.[method]?.requestBody?.content;
            expect(Object.keys(content ?? {})).toContain("multipart/form-data");
         }
      );

      it("leaves no FastAPI Body_* artifact components behind", () => {
         const api = JSON.parse(fs.readFileSync(API_SPEC_PATH, "utf8")) as {
            components?: { schemas?: Record<string, unknown> };
         };
         const leftovers = Object.keys(api.components?.schemas ?? {}).filter(
            (name) => name.startsWith("Body_")
         );

         expect(leftovers).toEqual([]);
      });
   });
});
