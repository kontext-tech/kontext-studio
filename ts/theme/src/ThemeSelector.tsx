import { ThemeMode } from "./themeMode";
import {
   MoonOutlined,
   SunMoonOutlined,
   SunOutlined
} from "@kontext-labs/icons";
import { Button, Dropdown } from "antd";
import type React from "react";
import { themeMenuItems } from "./themeMenuItems";
import { useTheme } from "./useTheme";

export interface ThemeSelectorProps {
   showText?: boolean;
   buttonStyle?: React.CSSProperties;
   labelPrefix?: string;
   placement?:
      "bottom" | "bottomLeft" | "bottomRight" | "top" | "topLeft" | "topRight";
}

function ThemeSelector({
   showText = false,
   buttonStyle,
   labelPrefix = "",
   placement = "bottomRight"
}: ThemeSelectorProps) {
   const { themeMode, handleThemeModeChange } = useTheme();

   const menuItems = themeMenuItems(handleThemeModeChange);

   const getThemeIcon = () => {
      switch (themeMode) {
         case ThemeMode.System:
            return <SunMoonOutlined />;
         case ThemeMode.Dark:
            return <MoonOutlined />;
         case ThemeMode.Light:
         default:
            return <SunOutlined />;
      }
   };

   const getButtonText = () => {
      switch (themeMode) {
         case ThemeMode.Light:
            return "Light";
         case ThemeMode.Dark:
            return "Dark";
         case ThemeMode.System:
         default:
            return "System";
      }
   };

   return (
      <Dropdown
         menu={{ items: menuItems, selectedKeys: [themeMode] }}
         trigger={["click"]}
         placement={placement}
      >
         <Button
            type="text"
            title="Change theme"
            icon={getThemeIcon()}
            style={{
               cursor: "pointer",
               display: "flex",
               alignItems: "center",
               gap: showText ? 8 : 0,
               ...buttonStyle
            }}
         >
            {showText && `${labelPrefix}${getButtonText()}`}
         </Button>
      </Dropdown>
   );
}

export default ThemeSelector;
