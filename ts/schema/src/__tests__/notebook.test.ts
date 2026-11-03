import { NotebookDocumentSchema } from "../notebook/document";

describe("Notebook schemas", () => {
   it("rejects non-python code block languages", () => {
      const invalidDocument = {
         title: "Notebook",
         created: 1,
         modified: 1,
         blocks: [
            {
               id: "11111111-1111-1111-1111-111111111111",
               type: "code",
               data: {
                  code: "print('hello')",
                  language: "javascript"
               }
            }
         ]
      };

      expect(() => NotebookDocumentSchema.parse(invalidDocument)).toThrow();
   });

   it("rejects header blocks that use level 1", () => {
      const invalidDocument = {
         title: "Legacy Notebook",
         created: 1,
         modified: 1,
         blocks: [
            {
               id: "11111111-1111-1111-1111-111111111111",
               type: "header",
               data: {
                  text: "Notebook Title",
                  level: 1
               }
            }
         ]
      };

      expect(() => NotebookDocumentSchema.parse(invalidDocument)).toThrow();
   });

   // A freshly inserted block has empty/placeholder data. These states are
   // persisted (a user can save with an empty block) and must round-trip,
   // otherwise reloading the notebook fails validation and empties it. See the
   // "empty notebook after save" regression.
   const parseWithBlock = (data: Record<string, unknown>, type: string) =>
      NotebookDocumentSchema.parse({
         title: "Notebook",
         created: 1,
         modified: 1,
         blocks: [
            {
               id: "11111111-1111-1111-1111-111111111111",
               type,
               data
            }
         ]
      });

   it("accepts an empty paragraph block", () => {
      expect(() => parseWithBlock({ text: "" }, "paragraph")).not.toThrow();
   });

   it("accepts an empty header block", () => {
      expect(() =>
         parseWithBlock({ text: "", level: 2 }, "header")
      ).not.toThrow();
   });

   it("accepts an empty quote block", () => {
      expect(() => parseWithBlock({ text: "" }, "quote")).not.toThrow();
   });

   it("accepts an empty code (python) block", () => {
      expect(() =>
         parseWithBlock({ code: "", language: "python" }, "code")
      ).not.toThrow();
   });

   it("accepts an empty SQL block", () => {
      expect(() =>
         parseWithBlock({ title: "SQL Query", code: "" }, "sql")
      ).not.toThrow();
   });

   it("accepts an empty mermaid block", () => {
      expect(() => parseWithBlock({ code: "" }, "mermaid")).not.toThrow();
   });

   it("accepts an empty list block", () => {
      expect(() =>
         parseWithBlock({ style: "unordered", items: [], meta: {} }, "list")
      ).not.toThrow();
   });

   it("accepts an empty table block", () => {
      expect(() => parseWithBlock({ content: [] }, "table")).not.toThrow();
   });

   it("accepts an image block without a caption", () => {
      expect(() =>
         parseWithBlock({ file: { url: "https://example.com/a.png" } }, "image")
      ).not.toThrow();
   });
});
