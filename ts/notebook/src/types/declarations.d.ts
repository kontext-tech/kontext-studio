declare module "*.notebook?raw" {
   const content: string; // Declare that importing it yields a NotebookDocument
   export default content;
}
