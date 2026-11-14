import AppHeader from "@/components/layout/AppHeader";
import AppSidebarFooter from "@/components/layout/AppSidebarFooter";
import AppSidebarTop from "@/components/layout/AppSidebarTop";
import PythonEnvironmentBanner from "@/components/layout/PythonEnvironmentBanner";
import { AppShellLayout, type AppShellLayoutProps } from "@kontext-tech/layout";
import { useTheme } from "@kontext-tech/theme";
import React, { type ReactNode } from "react";

interface MenuProps {
   collapsed: boolean;
   isDarkMode: boolean;
   isSmallScreen: boolean;
   smallLogo: string;
   siteLogo: string;
}

interface BaseLayoutProps {
   renderSideMenu: (props: MenuProps) => ReactNode;
   centerContent?: boolean;
   maxWidth?: number | string;
   contentPadding?: number | string;
   showProjectSelector?: boolean;
   fullHeight?: boolean;
}

const BaseLayout: React.FC<BaseLayoutProps> = ({
   renderSideMenu,
   centerContent = false,
   maxWidth = "100%",
   contentPadding = "auto",
   showProjectSelector = false,
   fullHeight = false
}) => {
   const { isDarkMode, siteLogo, smallLogo } = useTheme();

   const sharedLayoutProps: AppShellLayoutProps = {
      renderHeader: ({
         collapsed,
         setCollapsed,
         isSmallScreen,
         toggleDrawer
      }) => (
         <AppHeader
            collapsed={collapsed}
            setCollapsed={setCollapsed}
            isSmallScreen={isSmallScreen}
            toggleDrawer={toggleDrawer}
            siteLogo={siteLogo}
            smallLogo={smallLogo}
            showProjectSelector={showProjectSelector}
         />
      ),
      renderSidebarTop: ({ collapsed, isSmallScreen, toggleCollapsed }) => (
         <AppSidebarTop
            collapsed={collapsed}
            isSmallScreen={isSmallScreen}
            onToggleCollapsed={toggleCollapsed}
            siteLogo={siteLogo}
            smallLogo={smallLogo}
            showProjectSelector={showProjectSelector}
         />
      ),
      renderSideMenu: ({ collapsed, isSmallScreen }) =>
         renderSideMenu({
            collapsed,
            isDarkMode,
            isSmallScreen,
            smallLogo,
            siteLogo
         }),
      renderSidebarFooter: ({ collapsed }) => (
         <AppSidebarFooter collapsed={collapsed} />
      ),
      desktopHeaderMode: "hidden",
      centerContent,
      maxWidth,
      contentPadding,
      fullHeight,
      banner: <PythonEnvironmentBanner />
   };

   return <AppShellLayout {...sharedLayoutProps} />;
};

export default BaseLayout;
