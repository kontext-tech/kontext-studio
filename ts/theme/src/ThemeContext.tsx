import { LOCAL_STORAGE_KEYS } from "@kontext-labs/common/constants";
import { ThemeMode } from "./themeMode";
import type { ThemeConfig } from "antd";
import {
   createContext,
   type ReactNode,
   useEffect,
   useMemo,
   useState
} from "react";
import { createThemeConfig } from "./antd";

export interface ThemeContextProps {
   isDarkMode: boolean;
   themeMode: ThemeMode;
   handleThemeModeChange: (mode: ThemeMode) => void;
   themeConfig: ThemeConfig;
   siteLogo: string;
   smallLogo: string;
}

export interface ThemeProviderProps {
   children: ReactNode;
}

const readStoredThemeMode = (): ThemeMode => {
   if (typeof window === "undefined") {
      return ThemeMode.System;
   }

   const savedMode = window.localStorage.getItem(LOCAL_STORAGE_KEYS.THEME_MODE);

   if (!savedMode) {
      return ThemeMode.System;
   }

   try {
      const parsed = JSON.parse(savedMode);

      if (Object.values(ThemeMode).includes(parsed as ThemeMode)) {
         return parsed as ThemeMode;
      }
   } catch {
      // Ignore corrupted local storage and fall back to the default.
   }

   return ThemeMode.System;
};

const getSystemDarkPreference = (): boolean => {
   if (typeof window === "undefined") {
      return false;
   }

   return window.matchMedia("(prefers-color-scheme: dark)").matches;
};

export const ThemeContext = createContext<ThemeContextProps | undefined>(
   undefined
);

export function ThemeProvider({ children }: ThemeProviderProps) {
   const [themeMode, setThemeMode] = useState<ThemeMode>(readStoredThemeMode);
   const [systemIsDarkMode, setSystemIsDarkMode] = useState<boolean>(
      getSystemDarkPreference
   );

   const isDarkMode =
      themeMode === ThemeMode.System
         ? systemIsDarkMode
         : themeMode === ThemeMode.Dark;

   const siteLogo = isDarkMode
      ? "/resources/logo-dark.svg"
      : "/resources/logo.svg";
   const smallLogo = "/resources/logo-small.svg";

   const themeConfig = useMemo(
      () => createThemeConfig(isDarkMode),
      [isDarkMode]
   );

   useEffect(() => {
      if (typeof window === "undefined") {
         return undefined;
      }

      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleSystemThemeChange = (event: MediaQueryListEvent) => {
         setSystemIsDarkMode(event.matches);
      };

      mediaQuery.addEventListener("change", handleSystemThemeChange);

      return () => {
         mediaQuery.removeEventListener("change", handleSystemThemeChange);
      };
   }, [themeMode]);

   useEffect(() => {
      if (typeof window === "undefined") {
         return;
      }

      window.localStorage.setItem(
         LOCAL_STORAGE_KEYS.THEME_MODE,
         JSON.stringify(themeMode)
      );
   }, [themeMode]);

   const handleThemeModeChange = (mode: ThemeMode) => {
      setThemeMode(mode);
   };

   return (
      <ThemeContext.Provider
         value={{
            isDarkMode,
            themeMode,
            handleThemeModeChange,
            themeConfig,
            siteLogo,
            smallLogo
         }}
      >
         {children}
      </ThemeContext.Provider>
   );
}
