/**
 * TanStack Query keys for file-domain content, shared by this package and the
 * app so invalidations and cache reads use the same tuples.
 */
export const fileKeys = {
   fileResource: (fileId: string | undefined, projectId: string | undefined) =>
      ["file-resource", fileId, projectId] as const,
   inlineDataFile: (
      fileId: string | undefined,
      projectId: string | undefined
   ) => ["inline-data-file", fileId, projectId] as const,
   chartDataRef: (dataId: string | undefined, projectId: string | undefined) =>
      ["chart-data-ref", dataId, projectId] as const
};
