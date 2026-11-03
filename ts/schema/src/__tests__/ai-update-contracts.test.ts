import {
   QuerySessionStatus,
   UpdateChatSessionRequestSchema,
   UpdateQuerySessionRequestSchema
} from "..";

describe("AI update request contracts", () => {
   it("treats all chat-session update fields as omission-only", () => {
      expect(
         UpdateChatSessionRequestSchema.parse({
            defaultNamespace: "finance"
         })
      ).toMatchObject({
         defaultNamespace: "finance"
      });
   });

   it("rejects null for omission-only chat-session update fields", () => {
      expect(
         UpdateChatSessionRequestSchema.safeParse({
            modelSelectionId: null
         }).success
      ).toBe(false);

      expect(
         UpdateChatSessionRequestSchema.safeParse({
            defaultNamespace: null
         }).success
      ).toBe(false);
   });

   it("rejects null for omission-only query-session update fields", () => {
      expect(
         UpdateQuerySessionRequestSchema.safeParse({
            sessionName: null
         }).success
      ).toBe(false);

      expect(
         UpdateQuerySessionRequestSchema.safeParse({
            metadata: null
         }).success
      ).toBe(false);

      expect(
         UpdateQuerySessionRequestSchema.parse({
            status: QuerySessionStatus.Closed
         })
      ).toMatchObject({
         status: QuerySessionStatus.Closed
      });
   });
});
