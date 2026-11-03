import { useMemo } from "react";
import type { UiFeedback } from "../types";
import { useUiApp } from "./useUiApp";

export const useUiFeedback = (): UiFeedback => {
   const app = useUiApp();

   return useMemo(
      () => ({
         success: (content: string) => app.message.success(content),
         error: (content: string) => app.message.error(content),
         info: (content: string) => app.message.info(content),
         warning: (content: string) => app.message.warning(content),
         confirm: (options) => {
            void app.modal.confirm(options);
         }
      }),
      [app]
   );
};
