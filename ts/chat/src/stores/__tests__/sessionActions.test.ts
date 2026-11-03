/// <reference types="jest" />

import { createSessionActions } from "../sessionActions";
import type { RecentSessionsCache, StoreContext } from "../storeContextTypes";

/**
 * The extracted factories take a plain `StoreContext`, so these tests drive them
 * with a hand-rolled fake instead of a real zustand store. That keeps the
 * assertions on behaviour (cache TTL, in-flight dedup, error branches) rather
 * than on store wiring, which `chatSessionStore.test.ts` already covers.
 */
const createFakeContext = () => {
   /**
    * `fetchRecentSessions` is part of the state because several actions trigger a
    * background refresh via `get().fetchRecentSessions(...)`. Without it those
    * calls would throw and make every mutating action look like a failure.
    */
   const fetchRecentSessions = jest.fn(async () => {});

   const state: Record<string, unknown> = {
      chatService: null,
      projectId: "project-1",
      chatSession: null,
      modelSelectionId: "model-1",
      messages: [],
      artifacts: [],
      recentSessions: [],
      totalSessions: 0,
      mySessionsOnly: false,
      fetchRecentSessions,
      isMessagesLoading: false,
      error: null,
      artifactRuntimeById: {}
   };

   const recentSessionsCache: RecentSessionsCache = {
      request: null,
      key: null,
      fetchedAt: 0
   };

   const ctx: StoreContext = {
      get: () => state as never,
      set: (partial) => {
         const next =
            typeof partial === "function"
               ? (partial as (s: never) => Record<string, unknown>)(
                    state as never
                 )
               : partial;
         Object.assign(state, next);
      },
      recentSessionsCache
   };

   return {
      ctx,
      /** Current state after all `set()` calls applied. */
      patch: () => state,
      fetchRecentSessions,
      recentSessionsCache
   };
};

const paginatedSessions = (items: { id: string }[], totalCount?: number) =>
   ({
      succeed: true,
      data: {
         items: items.map((item) => ({ id: item.id })),
         totalCount: totalCount ?? items.length
      }
   }) as never;

const withSessionService = (
   ctx: StoreContext,
   getFilteredChatSessions: jest.Mock
) => {
   ctx.get = () =>
      ({
         chatService: { getFilteredChatSessions },
         projectId: "project-1"
      }) as never;
};

describe("sessionActions.fetchRecentSessions", () => {
   it("skips the fetch when the service or project is not initialized", async () => {
      const { ctx, recentSessionsCache } = createFakeContext();
      const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions();

      expect(warn).toHaveBeenCalledWith(
         expect.stringContaining("skipping fetchRecentSessions")
      );
      // Cache must stay untouched so a later call can still fetch.
      expect(recentSessionsCache.key).toBeNull();
      warn.mockRestore();
   });

   it("fetches, then serves the second call from cache", async () => {
      const { ctx, patch, recentSessionsCache } = createFakeContext();
      const getFilteredChatSessions = jest.fn(async () =>
         paginatedSessions([{ id: "session-1" }])
      );
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions();
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(1);

      // Same key, within TTL -> served from cache, no second network call.
      await actions.fetchRecentSessions();
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(1);
      expect(recentSessionsCache.fetchedAt).toBeGreaterThan(0);
      expect(patch().recentSessions).toEqual([{ id: "session-1" }]);
      expect(patch().totalSessions).toBe(1);
   });

   it("re-fetches when the TTL has expired", async () => {
      const { ctx, recentSessionsCache } = createFakeContext();
      const getFilteredChatSessions = jest.fn(async () =>
         paginatedSessions([{ id: "session-1" }])
      );
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions();
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(1);

      // Push the recorded fetch beyond the 30s TTL without waiting.
      recentSessionsCache.fetchedAt = Date.now() - 30_001;

      await actions.fetchRecentSessions();
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(2);
   });

   it("re-fetches with force even while the cache is fresh", async () => {
      const { ctx } = createFakeContext();
      const getFilteredChatSessions = jest.fn(async () =>
         paginatedSessions([{ id: "session-1" }])
      );
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions();
      await actions.fetchRecentSessions(false, { force: true });

      expect(getFilteredChatSessions).toHaveBeenCalledTimes(2);
   });

   it("de-duplicates concurrent calls for the same key", async () => {
      const { ctx } = createFakeContext();
      let resolveFetch: ((value: never) => void) | undefined;
      const getFilteredChatSessions = jest.fn(
         () =>
            new Promise((resolve) => {
               resolveFetch = resolve as (value: never) => void;
            }) as Promise<never>
      );
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      const first = actions.fetchRecentSessions();
      const second = actions.fetchRecentSessions();

      resolveFetch?.(paginatedSessions([{ id: "session-1" }]));
      await Promise.all([first, second]);

      // The second call joins the in-flight promise instead of issuing its own.
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(1);
   });

   it("clears the in-flight request and keeps the cache cold on failure", async () => {
      const { ctx, recentSessionsCache } = createFakeContext();
      const getFilteredChatSessions = jest.fn(async () => ({
         succeed: false,
         error: { title: "boom", status: 500, messages: [] }
      }));
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions();

      expect(recentSessionsCache.request).toBeNull();
      // fetchedAt must not advance, otherwise failures would be cached.
      expect(recentSessionsCache.fetchedAt).toBe(0);
   });
});

describe("sessionActions guard branches", () => {
   it("reports an error and returns null when the chat service is missing", async () => {
      const { ctx, patch } = createFakeContext();
      const actions = createSessionActions(ctx);

      await expect(actions.createChatSession("New")).resolves.toBeNull();
      expect(patch().error).toBe(
         "Chat service not initialized. Call initializeChatService first."
      );
   });

   it("reports an error and returns null when the project is missing", async () => {
      const { ctx, patch } = createFakeContext();
      patch().chatService = {};
      patch().projectId = null;
      const actions = createSessionActions(ctx);

      await expect(actions.createChatSession("New")).resolves.toBeNull();
      expect(patch().error).toBe("Project not initialized");
   });

   it("surfaces the thrown message from createChatSession", async () => {
      const { ctx, patch } = createFakeContext();
      patch().chatService = {
         createChatSession: async () => {
            throw new Error("network down");
         }
      };
      const actions = createSessionActions(ctx);

      await expect(actions.createChatSession("New")).resolves.toBeNull();
      expect(patch().error).toBe("network down");
   });

   it("creates new sessions with the scoped options", async () => {
      const { ctx, patch, fetchRecentSessions } = createFakeContext();
      const createChatSession = jest.fn(async () => ({
         succeed: true,
         data: { id: "session-1", projectId: "project-1" }
      }));
      patch().chatService = { createChatSession };
      const actions = createSessionActions(ctx);

      await expect(actions.createChatSession("New")).resolves.toEqual({
         id: "session-1",
         projectId: "project-1"
      });
      expect(createChatSession).toHaveBeenCalledWith(
         expect.objectContaining({
            projectId: "project-1",
            modelSelectionId: "model-1",
            pythonExecutionApprovalMode: "always_ask"
         })
      );
      expect(patch().chatSession).toEqual({
         id: "session-1",
         projectId: "project-1"
      });
      // A successful create forces the recent-sessions list to refresh.
      expect(fetchRecentSessions).toHaveBeenCalledWith(false, { force: true });
   });

   it("returns a failed ApiResult from getFilteredChatSessions when uninitialized", async () => {
      const { ctx } = createFakeContext();
      const actions = createSessionActions(ctx);

      const result = await actions.getFilteredChatSessions();

      expect(result.succeed).toBe(false);
      expect(result.error?.status).toBe(500);
   });

   it("requires an active session before changing the approval mode", async () => {
      const { ctx, patch } = createFakeContext();
      patch().chatService = {};
      patch().chatSession = null;
      const actions = createSessionActions(ctx);

      await expect(
         actions.setPythonExecutionApprovalMode("always_ask")
      ).resolves.toBe(false);
      expect(patch().error).toBe(
         "Active chat session is required to update Python approval mode."
      );
   });
});

describe("sessionActions.fetchRecentSessions (request key)", () => {
   it("re-fetches when the request key changes", async () => {
      const { ctx } = createFakeContext();
      const getFilteredChatSessions = jest.fn(async () =>
         paginatedSessions([{ id: "session-1" }])
      );
      withSessionService(ctx, getFilteredChatSessions);
      const actions = createSessionActions(ctx);

      await actions.fetchRecentSessions(false);
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(1);

      // `mySessionsOnly` is part of the key -> a different key is not cached.
      await actions.fetchRecentSessions(true);
      expect(getFilteredChatSessions).toHaveBeenCalledTimes(2);
   });
});
