/**
 * Comprehensive test suite for Core API schemas generated from OpenAPI specification
 */

import * as CoreAPI from "../core";

describe("Core API Schemas", () => {
   describe("Schema Exports", () => {
      it("should export all expected schemas", () => {
         // Test that major schemas are exported
         expect(CoreAPI.AccessLevelSchema).toBeDefined();
         expect(CoreAPI.ProjectModelSchema).toBeDefined();
         expect(CoreAPI.RoleModelSchema).toBeDefined();
      });

      it("should provide proper TypeScript types", () => {
         // Test that types are properly inferred
         const accessLevel: CoreAPI.AccessLevel = "Private";
         expect(accessLevel).toBe("Private");

         // This should compile without errors if types are correct
         const project: Partial<CoreAPI.ProjectModel> = {
            projectName: "Test",
            projectDescription: "A test project"
         };
         expect(project.projectName).toBe("Test");
      });
   });

   describe("Enum Validation", () => {
      it("should validate enum schemas correctly", () => {
         // Test AccessLevel enum
         expect(CoreAPI.AccessLevelSchema.parse("Private")).toBe("Private");
         expect(CoreAPI.AccessLevelSchema.parse("Public")).toBe("Public");
         expect(() => CoreAPI.AccessLevelSchema.parse("Invalid")).toThrow();
      });

      it("should handle enum default values", () => {
         // AccessLevel enum test
         const schema = CoreAPI.AccessLevelSchema;

         // Should accept valid values
         expect(schema.parse("Private")).toBe("Private");
         expect(schema.parse("Public")).toBe("Public");

         // Should reject invalid values
         expect(() => schema.parse("InvalidValue")).toThrow();
      });
   });

   describe("Object Schema Validation", () => {
      it("should validate simple object schemas correctly", () => {
         // Test a simple object schema
         const validAccessToken = {
            tokenType: "Bearer",
            accessToken: "abc123",
            expiresIn: 3600,
            refreshToken: "refresh123"
         };

         const result =
            CoreAPI.AccessTokenResponseSchema.parse(validAccessToken);
         expect(result).toEqual(validAccessToken);
      });

      it("should handle optional and nullable fields", () => {
         // Test schema with required fields only
         const minimalProject = {
            configuration: {
               allowedFileTypes: [],
               maxFileBytesSize: 1000000,
               totalStorageAllocationBytes: 10000000,
               features: []
            },
            id: "123e4567-e89b-12d3-a456-426614174000",
            projectName: "Test Project",
            projectCode: "test-project",
            ownerId: "123e4567-e89b-12d3-a456-426614174001"
         };

         // This should not throw since we provide all required fields
         const result = CoreAPI.ProjectModelSchema.parse(minimalProject);
         expect(result).toMatchObject(minimalProject);

         // Test that optional fields can be undefined
         expect(result.projectDescription).toBeUndefined();
      });

      it("should reject legacy project configuration fields", () => {
         const configWithLegacyFields = {
            allowedFileTypes: [],
            maxFileBytesSize: 1000000,
            totalStorageAllocationBytes: 10000000,
            features: [],
            allowed_llm_model_ids: ["legacy-model"],
            is_local: true
         };

         const result = CoreAPI.ProjectConfigurationSchema.safeParse(
            configWithLegacyFields
         );

         expect(result.success).toBe(false);
      });

      it("should validate complex objects with property descriptions", () => {
         const validProject = {
            id: "123e4567-e89b-12d3-a456-426614174000",
            projectName: "Test Project",
            projectCode: "TEST",
            ownerId: "123e4567-e89b-12d3-a456-426614174001",
            configuration: {
               allowedFileTypes: [],
               maxFileBytesSize: 1000000,
               totalStorageAllocationBytes: 10000000,
               features: []
            }
         };

         const result = CoreAPI.ProjectModelSchema.safeParse(validProject);
         expect(result.success).toBe(true);
      });

      it("should validate role schema", () => {
         const validRole = {
            id: "123e4567-e89b-12d3-a456-426614174000",
            name: "Test Role",
            isSystemRole: false,
            isProjectScopedRole: true,
            isSelected: false,
            claims: []
         };

         const result = CoreAPI.RoleModelSchema.safeParse(validRole);
         expect(result.success).toBe(true);
      });
   });

   describe("String Validation Features", () => {
      it("should handle string length constraints", () => {
         // Test AddJobRunLogRequest.message with minLength: 0, maxLength: 2000
         const validMessage = "A".repeat(1000); // Within bounds
         const tooLongMessage = "A".repeat(2001); // Exceeds maxLength

         const validRequest = {
            level: "Information", // LogLevel enum value
            message: validMessage
         };

         expect(() =>
            CoreAPI.AddJobRunLogRequestSchema.parse(validRequest)
         ).not.toThrow();

         const invalidRequest = {
            level: "Information",
            message: tooLongMessage
         };

         expect(() =>
            CoreAPI.AddJobRunLogRequestSchema.parse(invalidRequest)
         ).toThrow();
      });

      it("should provide helpful error messages for invalid types", () => {
         const invalidProject = {
            id: "123e4567-e89b-12d3-a456-426614174000",
            projectName: 123, // Should be string
            projectCode: "TEST",
            configuration: {
               allowedFileTypes: [],
               maxFileBytesSize: 1000000,
               totalStorageAllocationBytes: 10000000
            }
         };

         const result = CoreAPI.ProjectModelSchema.safeParse(invalidProject);
         expect(result.success).toBe(false);

         if (!result.success) {
            expect(result.error.issues[0].path).toContain("projectName");
            expect(result.error.issues[0].code).toBe("invalid_type");
         }
      });
   });

   describe("Record Types (Dynamic Properties)", () => {
      it("should handle complex record types", () => {
         // Test projectRoles: z.record(z.string(), z.array(z.string()))
         const userWithRoles = {
            id: "123e4567-e89b-12d3-a456-426614174000",
            firstName: "Test",
            projectRoles: {
               project1: ["admin", "editor"],
               project2: ["viewer"],
               project3: []
            }
         };

         // This should work (partial validation)
         expect(() => {
            const parsed =
               CoreAPI.UserWithRolesModelSchema.parse(userWithRoles);
            expect(parsed.projectRoles).toBeDefined();
         }).not.toThrow();
      });
   });

   describe("Property Descriptions", () => {
      it("should handle optional fields with descriptions correctly", () => {
         const projectWithOptionals = {
            id: "123e4567-e89b-12d3-a456-426614174000",
            projectCode: "test",
            projectName: "Test Project",
            configuration: {
               allowedFileTypes: [],
               maxFileBytesSize: 1000000,
               totalStorageAllocationBytes: 10000000,
               features: []
            },
            projectDescription: "A test project",
            ownerId: "123e4567-e89b-12d3-a456-426614174001"
         };

         const result =
            CoreAPI.ProjectModelSchema.safeParse(projectWithOptionals);
         expect(result.success).toBe(true);

         if (result.success) {
            expect(result.data.projectName).toBe("Test Project");
            expect(result.data.projectDescription).toBe("A test project");
         }
      });
   });

   describe("Backward Compatibility", () => {
      it("should maintain backward compatibility", () => {
         // Ensure existing functionality still works
         const accessLevel: CoreAPI.AccessLevel = "Private";
         expect(accessLevel).toBe("Private");

         // Ensure validation still works for regular schemas
         const accessToken = {
            tokenType: "Bearer",
            accessToken: "abc123",
            expiresIn: 3600,
            refreshToken: "refresh123"
         };

         expect(() =>
            CoreAPI.AccessTokenResponseSchema.parse(accessToken)
         ).not.toThrow();
      });
   });

   describe("InlineData", () => {
      const base = {
         title: "data",
         table: { columns: [], rows: [], rowCount: 0 }
      };

      it("accepts a null metadata field (absent provenance is serialized as null)", () => {
         expect(() =>
            CoreAPI.InlineDataSchema.parse({ ...base, metadata: null })
         ).not.toThrow();
      });

      it("accepts an omitted metadata field", () => {
         expect(() => CoreAPI.InlineDataSchema.parse(base)).not.toThrow();
      });

      it("accepts a present metadata object", () => {
         expect(() =>
            CoreAPI.InlineDataSchema.parse({
               ...base,
               metadata: { rowCount: 5, dataPath: ".data/x.parquet" }
            })
         ).not.toThrow();
      });

      it("rejects a non-object metadata value", () => {
         expect(() =>
            CoreAPI.InlineDataSchema.parse({ ...base, metadata: 5 })
         ).toThrow();
      });

      it("accepts FastAPI-style nulls for unset optional fields", () => {
         // The API serializes unset optionals as null rather than omitting them.
         const payload = {
            title: "t",
            table: {
               columns: [{ name: "a", type: "VARCHAR", isNullable: null }],
               rows: [["x"]],
               rowCount: 1
            },
            metadata: {
               notebookId: null,
               querySessionId: null,
               chatSessionId: "11111111-1111-1111-1111-111111111111",
               sql: null,
               createdAt: null,
               dataPath: ".data/x.parquet",
               rowCount: 5
            }
         };
         expect(() => CoreAPI.InlineDataSchema.parse(payload)).not.toThrow();
      });

      it("still rejects wrong optional field types", () => {
         expect(() =>
            CoreAPI.InlineDataSchema.parse({
               title: "t",
               table: {
                  columns: [{ name: "a", type: "VARCHAR", isNullable: "yes" }],
                  rows: [],
                  rowCount: 1
               }
            })
         ).toThrow();
      });
   });
});
