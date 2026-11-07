import { useUserStore } from "@kontext-tech/identity";

type ModuleLoader = () => Promise<unknown>;

const AUTHENTICATED_PRELOADERS: ModuleLoader[] = [
   () => import("../features/account/screens/AccountPage")
];

const ANONYMOUS_PRELOADERS: ModuleLoader[] = [
   () => import("../features/auth/screens/LoginPage")
];

let preloadScheduled = false;

const canPreloadOnCurrentConnection = (): boolean => {
   if (typeof navigator === "undefined") {
      return false;
   }

   const connection = (
      navigator as Navigator & {
         connection?: { saveData?: boolean; effectiveType?: string };
      }
   ).connection;

   if (!connection) {
      return true;
   }

   if (connection.saveData) {
      return false;
   }

   return connection.effectiveType !== "2g";
};

const scheduleIdleTask = (task: () => void): void => {
   const idleScheduler = (
      globalThis as typeof globalThis & {
         requestIdleCallback?: (callback: () => void) => number;
      }
   ).requestIdleCallback;

   if (idleScheduler) {
      idleScheduler(task);
      return;
   }

   window.setTimeout(task, 400);
};

const preloadSequentially = (loaders: ModuleLoader[]): void => {
   let currentIndex = 0;

   const runNext = () => {
      const nextLoader = loaders[currentIndex];
      currentIndex += 1;

      if (!nextLoader) {
         return;
      }

      void nextLoader().finally(() => {
         scheduleIdleTask(runNext);
      });
   };

   scheduleIdleTask(runNext);
};

export const scheduleLikelyRoutePreloads = (): void => {
   if (preloadScheduled || typeof window === "undefined") {
      return;
   }

   preloadScheduled = true;

   if (!canPreloadOnCurrentConnection()) {
      return;
   }

   const isAuthenticated = useUserStore.getState().isAuthenticated;
   const preloaders = isAuthenticated
      ? AUTHENTICATED_PRELOADERS
      : ANONYMOUS_PRELOADERS;

   preloadSequentially(preloaders);
};
