/**
 * Cross-package notebook addressing.
 *
 * The per-notebook editor instance id convention shared by the editor store
 * (ts/notebook), chat HITL flows (ts/chat) and app host bindings.
 */

/** Canonical per-notebook editor instance id used by the editor store. */
export const notebookInstanceId = (notebookId: string): string =>
   `notebook-${notebookId}`;
