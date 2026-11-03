/**
 * Single canonical declaration of the browser environment object.
 *
 * Programs that read `window.ENV` must add this file to their tsconfig
 * `files` instead of redeclaring it: duplicate `Window.ENV` declarations merge
 * silently and drift (each package saw a different shape) — exactly the bug
 * this consolidation removes.
 */
declare global {
   interface Window {
      ENV?: {
         PUBLIC_KONTEXT_API_URL?: string;
         PUBLIC_KONTEXT_DATA_API_URL?: string;
         PUBLIC_KONTEXT_URL?: string;
         PUBLIC_KONTEXT_APP_URL?: string;
         PUBLIC_KONTEXT_UPDATES_PROJECT_ID?: string;
         KONTEXT_LOCAL_MODE?: string;
         VERSION?: string;
         IS_DEVELOPMENT?: boolean;
      };
   }
}

export {};
