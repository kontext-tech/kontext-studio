import { theme, type ThemeConfig } from "antd";
import { tokens } from "./tokens";

export const getThemeTokens = () => {
   const { token } = theme.useToken();
   return token;
};

export const createThemeConfig = (isDark: boolean): ThemeConfig => {
   const { darkAlgorithm, defaultAlgorithm } = theme;
   const algorithm = isDark ? [darkAlgorithm] : defaultAlgorithm;
   const t = isDark ? tokens.dark : tokens.light;

   return {
      algorithm,
      token: {
         colorPrimary: t.primary,
         colorSuccess: t.success,
         colorWarning: t.warning,
         colorError: t.error,
         colorInfo: t.info,
         colorLink: t.primary,
         motion: false,
         borderRadius: tokens.shared.borderRadius
      },
      components: {
         Layout: {
            siderBg: isDark ? t.bgContainer : undefined
         },
         Drawer: {
            colorBgContainer: isDark ? t.bgContainer : undefined
         },
         Menu: {
            itemBg: "transparent",
            itemHoverBg: isDark
               ? "rgba(255, 255, 255, 0.1)"
               : "rgba(0, 0, 0, 0.04)",
            itemSelectedBg: isDark
               ? "rgba(255, 255, 255, 0.15)"
               : "rgba(0, 0, 0, 0.06)",
            darkItemBg: "transparent",
            darkItemSelectedColor: t.primary,
            darkItemSelectedBg: "rgba(255, 255, 255, 0.15)",
            darkItemHoverBg: "rgba(255, 255, 255, 0.1)",
            darkItemHoverColor: t.primary,
            itemBorderRadius: 50
         },
         Button: {
            borderRadius: 50,
            boxShadow: "none",
            primaryShadow: "none",
            defaultShadow: "none",
            fontWeight: 600
         },
         Tooltip: {
            borderRadius: tokens.shared.borderRadius
         },
         Spin: {
            dotSize: 20,
            dotSizeSM: 14,
            dotSizeLG: 32
         },
         CodeHighlighter: {
            colorBgTitle: isDark
               ? "rgba(255, 255, 255, 0.05)"
               : "rgba(0, 0, 0, 0.04)",
            colorBorderCode: isDark
               ? "rgba(255, 255, 255, 0.1)"
               : "rgba(0, 0, 0, 0.06)",
            colorTextTitle: isDark
               ? "rgba(255, 255, 255, 0.85)"
               : "rgba(0, 0, 0, 0.85)",
            colorFillContent: isDark
               ? "rgba(0, 0, 0, 0.5)"
               : "rgba(0, 0, 0, 0.02)"
         },
         Mermaid: {
            colorBgTitle: "transparent"
         }
      } as ThemeConfig["components"]
   };
};

export const getThemeStyles = (isDark = false) => {
   const t = isDark ? tokens.dark : tokens.light;
   return {
      colorPrimary: t.primary,
      colorSuccess: t.success,
      colorError: t.error,
      colorWarning: t.warning,
      colorInfo: t.info,
      colorBgContainer: t.bgContainer,
      colorBgElevated: t.bgElevated,
      colorBgLayout: t.bgLayout,
      colorBgSpotlight: t.bgSpotlight,
      colorBorder: t.border,
      colorBorderSecondary: t.borderSecondary,
      colorText: isDark ? "rgba(255, 255, 255, 0.85)" : "rgba(0, 0, 0, 0.88)",
      colorTextSecondary: isDark
         ? "rgba(255, 255, 255, 0.65)"
         : "rgba(0, 0, 0, 0.65)",
      colorTextTertiary: isDark
         ? "rgba(255, 255, 255, 0.45)"
         : "rgba(0, 0, 0, 0.45)",
      colorTextDisabled: isDark
         ? "rgba(255, 255, 255, 0.25)"
         : "rgba(0, 0, 0, 0.25)",
      borderRadius: tokens.shared.borderRadius,
      borderRadiusLG: tokens.shared.borderRadiusLG,
      borderRadiusSM: tokens.shared.borderRadiusSM,
      fontSizeSM: 12,
      fontSize: 14,
      fontSizeLG: 16,
      lineHeight: 1.5715,
      margin: 16,
      marginSM: 8,
      marginLG: 24,
      padding: 16,
      paddingSM: 12,
      paddingLG: 24,
      boxShadow: "none",
      boxShadowSecondary: "none"
   };
};
