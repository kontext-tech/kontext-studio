/**
 * Local launch-token handling.
 *
 * The local server prints a URL with `#token=...`; the fragment never reaches
 * the server or its logs. The app reads it once, removes it from the address
 * bar, and keeps it in sessionStorage for bootstrap and setup requests.
 */

export const LAUNCH_TOKEN_HEADER = "X-Kontext-Launch-Token";

const LAUNCH_TOKEN_STORAGE_KEY = "kontext.launch.token";

let cachedLaunchToken: string | undefined;

function getSessionStorage(): Storage | undefined {
   if (typeof window === "undefined") {
      return undefined;
   }
   try {
      return window.sessionStorage;
   } catch {
      return undefined;
   }
}

function storeLaunchToken(token: string): void {
   try {
      getSessionStorage()?.setItem(LAUNCH_TOKEN_STORAGE_KEY, token);
   } catch {
      // Storage can be unavailable in private or sandboxed contexts.
   }
}

/** Read `#token=...`, strip it from the URL, and return it. */
export function readLaunchTokenFromUrl(): string | undefined {
   if (typeof window === "undefined") {
      return undefined;
   }

   const rawHash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
   if (!rawHash) {
      return undefined;
   }

   const params = new URLSearchParams(rawHash);
   const token = params.get("token")?.trim();
   if (!token) {
      return undefined;
   }

   params.delete("token");
   const remainingHash = params.toString();
   const nextUrl = `${window.location.pathname}${window.location.search}${
      remainingHash ? `#${remainingHash}` : ""
   }`;
   try {
      window.history.replaceState(window.history.state, "", nextUrl);
   } catch {
      // Keep the token in memory even when the URL cannot be rewritten.
   }

   return token;
}

/** Return the launch token from memory, sessionStorage, or the URL fragment. */
export function getLaunchToken(): string | undefined {
   // A freshly printed URL wins over a token cached from an earlier server
   // run; otherwise restarting the server would leave the tab stuck on 401.
   const fromUrl = readLaunchTokenFromUrl();
   if (fromUrl) {
      cachedLaunchToken = fromUrl;
      storeLaunchToken(fromUrl);
      return fromUrl;
   }

   if (cachedLaunchToken) {
      return cachedLaunchToken;
   }

   const stored = getSessionStorage()?.getItem(LAUNCH_TOKEN_STORAGE_KEY);
   if (stored) {
      cachedLaunchToken = stored;
      return stored;
   }

   return undefined;
}

export function clearLaunchToken(): void {
   cachedLaunchToken = undefined;
   try {
      getSessionStorage()?.removeItem(LAUNCH_TOKEN_STORAGE_KEY);
   } catch {
      // Ignore storage failures during logout.
   }
}
