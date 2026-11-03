import { useCallback } from "react";
import { useBeforeUnload, useBlocker, useNavigate } from "react-router-dom";

/**
 * Custom hook to block navigation when there are unsaved changes.
 * Works with the router's built-in blocking APIs instead of mutating navigator internals.
 *
 * @param shouldBlock - Whether navigation should be blocked
 * @param message - Message to show in confirmation dialog
 */
export const useNavigationBlock = (
   shouldBlock: boolean,
   message: string = "You have unsaved changes. Are you sure you want to leave?"
) => {
   const navigate = useNavigate();

   const blocker = useBlocker(
      useCallback(() => {
         if (!shouldBlock) {
            return false;
         }

         return !window.confirm(message);
      }, [message, shouldBlock])
   );

   useBeforeUnload(
      useCallback(
         (event) => {
            if (!shouldBlock) return;

            event.preventDefault();
            event.returnValue = message;
         },
         [message, shouldBlock]
      )
   );

   const navigateWithoutConfirmation = useCallback(
      (to: string, options?: { replace?: boolean }) => {
         navigate(to, options);
      },
      [navigate]
   );

   const retryNavigation = useCallback(() => {
      if (blocker.state !== "blocked") return;

      blocker.proceed();
   }, [blocker]);

   const cancelNavigation = useCallback(() => {
      if (blocker.state !== "blocked") return;

      blocker.reset();
   }, [blocker]);

   return {
      navigateWithoutConfirmation,
      isBlocked: blocker.state === "blocked",
      retryNavigation,
      cancelNavigation
   };
};
