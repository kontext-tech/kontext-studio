import { ThemeContext } from "@kontext-labs/theme";
import { ConfigProvider, theme as antdTheme } from "antd";
import React from "react";
import { useNotebookStore } from "../stores/notebookStore";

type ThemeConfig = React.ComponentProps<typeof ConfigProvider>["theme"];

export interface NotebookThemeContextValue {
   isDarkMode: boolean;
   themeConfig?: ThemeConfig;
}

export function useTheme(instanceId?: string): NotebookThemeContextValue {
   const context = React.useContext(ThemeContext);
   const storeIsDarkMode = useNotebookStore(
      (state) =>
         state.getInstanceState(instanceId || "default")?.isDarkMode ?? false
   );
   const isDarkMode = context?.isDarkMode ?? storeIsDarkMode;
   const themeConfig = React.useMemo(
      () =>
         context?.themeConfig ?? {
            algorithm: isDarkMode
               ? antdTheme.darkAlgorithm
               : antdTheme.defaultAlgorithm
         },
      [context?.themeConfig, isDarkMode]
   );

   return React.useMemo(
      () => ({
         isDarkMode,
         themeConfig
      }),
      [isDarkMode, themeConfig]
   );
}
