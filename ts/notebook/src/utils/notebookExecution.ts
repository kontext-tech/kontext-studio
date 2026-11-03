const UUID_PATTERN =
   /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const resolveNotebookExecutionId = (
   notebookId: string | undefined,
   instanceId: string | undefined
): string | undefined => {
   if (notebookId) {
      return notebookId;
   }

   if (instanceId && UUID_PATTERN.test(instanceId)) {
      return instanceId;
   }

   return undefined;
};
