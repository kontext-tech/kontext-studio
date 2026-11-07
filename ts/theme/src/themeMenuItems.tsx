import {
   MoonOutlined,
   SunMoonOutlined,
   SunOutlined
} from "@kontext-tech/icons";
import type { MenuProps } from "antd";
import { ThemeMode } from "./themeMode";

/**
 * The three canonical theme menu entries (system/light/dark). Both the
 * `ThemeSelector` dropdown and app header submenus render from this so the
 * option set and icons cannot drift.
 */
export function themeMenuItems(
   handleThemeModeChange: (mode: ThemeMode) => void
): NonNullable<MenuProps["items"]> {
   return [
      {
         key: ThemeMode.System,
         icon: <SunMoonOutlined />,
         label: "Sync with system",
         onClick: () => handleThemeModeChange(ThemeMode.System)
      },
      {
         key: ThemeMode.Light,
         icon: <SunOutlined />,
         label: "Light",
         onClick: () => handleThemeModeChange(ThemeMode.Light)
      },
      {
         key: ThemeMode.Dark,
         icon: <MoonOutlined />,
         label: "Dark",
         onClick: () => handleThemeModeChange(ThemeMode.Dark)
      }
   ];
}

/** Human label for a theme mode ("System" | "Light" | "Dark"). */
export function themeModeLabel(mode: ThemeMode): string {
   switch (mode) {
      case ThemeMode.System:
         return "System";
      case ThemeMode.Dark:
         return "Dark";
      case ThemeMode.Light:
      default:
         return "Light";
   }
}
