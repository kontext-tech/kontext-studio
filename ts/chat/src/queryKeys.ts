/** TanStack Query keys for chat-domain read models. */
export const chatKeys = {
   modelCatalog: (accessToken?: string) =>
      ["modelCatalog", accessToken] as const
};
