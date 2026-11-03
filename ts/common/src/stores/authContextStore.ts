import { create } from "zustand";

/**
 * Service-seam projection of the auth token for `useService`/`useDataService`.
 *
 * The token's authority is the identity user store (`userStore.tokens`) — this
 * store is only written by `userStore` actions via `setAuthAccessToken`; other
 * modules must read, never write.
 */
interface AuthContextState {
   accessToken?: string;
   setAccessToken: (accessToken?: string) => void;
}

export const useAuthContextStore = create<AuthContextState>((set) => ({
   accessToken: undefined,
   setAccessToken: (accessToken) => set({ accessToken })
}));

export const setAuthAccessToken = (accessToken?: string) => {
   useAuthContextStore.getState().setAccessToken(accessToken);
};
