/**
 * Framework-free localStorage persistence for the Python-approval preference.
 *
 * Lives outside the React module so framework-free consumers (e.g.
 * `pythonHitl.ts`) do not pull in the approval modal's antd/React imports.
 */

import type { PythonExecutionApprovalMode } from "@kontext-tech/schema";

const PYTHON_APPROVAL_MODE_STORAGE_KEY =
   "kontext.chat.pythonExecutionApprovalMode";

export const loadRememberedPythonApprovalMode =
   (): PythonExecutionApprovalMode => {
      if (typeof window === "undefined") {
         return "always_ask";
      }

      try {
         const stored = window.localStorage.getItem(
            PYTHON_APPROVAL_MODE_STORAGE_KEY
         );
         return stored === "auto_approve" ? "auto_approve" : "always_ask";
      } catch {
         // Private mode / restricted storage: fall back to the safe default.
         return "always_ask";
      }
   };

export const persistRememberedPythonApprovalMode = (
   mode: PythonExecutionApprovalMode
): void => {
   if (typeof window === "undefined") {
      return;
   }

   try {
      window.localStorage.setItem(PYTHON_APPROVAL_MODE_STORAGE_KEY, mode);
   } catch {
      // Best-effort persistence; ignore quota/security errors.
   }
};
