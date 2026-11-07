import { PageErrorBoundary } from "@kontext-tech/ui";
import { Drawer, Grid, Layout, theme } from "antd";
import React, { type ReactNode, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import AppFooter from "./AppFooter";
import { LAYOUT } from "./constants";
import { useLayoutStore } from "./stores/layoutStore";

const { Sider, Content } = Layout;
const { useBreakpoint } = Grid;
const { useToken } = theme;

export interface AppShellMenuProps {
   collapsed: boolean;
   isSmallScreen: boolean;
   closeDrawer: () => void;
   toggleCollapsed: () => void;
}

export interface AppShellHeaderProps {
   collapsed: boolean;
   setCollapsed: (collapsed: boolean) => void;
   isSmallScreen: boolean;
   toggleDrawer: () => void;
}

export interface AppShellLayoutProps {
   renderHeader?: (props: AppShellHeaderProps) => ReactNode;
   renderSidebarTop?: (props: AppShellMenuProps) => ReactNode;
   renderSideMenu: (props: AppShellMenuProps) => ReactNode;
   renderSidebarFooter?: (props: AppShellMenuProps) => ReactNode;
   desktopHeaderMode?: "visible" | "hidden";
   centerContent?: boolean;
   maxWidth?: number | string;
   contentPadding?: number | string;
   fullHeight?: boolean;
   footer?: ReactNode;
}

const AppShellLayout: React.FC<AppShellLayoutProps> = ({
   renderHeader,
   renderSidebarTop,
   renderSideMenu,
   renderSidebarFooter,
   desktopHeaderMode = "visible",
   centerContent = false,
   maxWidth = "100%",
   contentPadding = "auto",
   fullHeight = false,
   footer
}) => {
   const { sideMenuCollapsed, setSideMenuCollapsed, toggleSideMenu } =
      useLayoutStore();
   const [drawerVisible, setDrawerVisible] = useState(false);
   const { token } = useToken();
   const screens = useBreakpoint();
   const isSmallScreen = !screens.md;
   const location = useLocation();
   const showDesktopHeader =
      !isSmallScreen &&
      desktopHeaderMode === "visible" &&
      typeof renderHeader === "function";
   const showMobileHeader = isSmallScreen && typeof renderHeader === "function";
   const viewportOffset =
      showDesktopHeader || showMobileHeader ? LAYOUT.HEADER_HEIGHT : 0;
   const viewportHeight =
      viewportOffset > 0 ? `calc(100vh - ${viewportOffset}px)` : "100vh";

   const menuProps: AppShellMenuProps = {
      collapsed: isSmallScreen ? false : sideMenuCollapsed,
      isSmallScreen,
      closeDrawer: () => setDrawerVisible(false),
      toggleCollapsed: toggleSideMenu
   };

   const headerProps: AppShellHeaderProps = {
      collapsed: sideMenuCollapsed,
      setCollapsed: setSideMenuCollapsed,
      isSmallScreen,
      toggleDrawer: () => setDrawerVisible((current) => !current)
   };

   const resolvedContentPadding =
      contentPadding === "auto" ? (isSmallScreen ? 16 : 24) : contentPadding;
   const resolvedPagePadding = isSmallScreen ? 16 : 24;
   const sidebarContent = (
      <div
         style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            background: token.colorBgElevated
         }}
      >
         {renderSidebarTop?.(menuProps)}
         <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
            {renderSideMenu(menuProps)}
         </div>
         {renderSidebarFooter?.(menuProps)}
      </div>
   );

   return (
      <Layout style={{ minHeight: "100vh" }}>
         {showDesktopHeader && renderHeader?.(headerProps)}
         {showMobileHeader && renderHeader?.(headerProps)}
         <Layout hasSider={!isSmallScreen}>
            {isSmallScreen ? (
               <Drawer
                  placement="left"
                  closable
                  onClose={() => setDrawerVisible(false)}
                  open={drawerVisible}
                  styles={{
                     body: {
                        padding: 0,
                        background: token.colorBgElevated,
                        display: "flex",
                        flexDirection: "column"
                     },
                     wrapper: { width: LAYOUT.SIDER_WIDTH_DRAWER }
                  }}
               >
                  {sidebarContent}
               </Drawer>
            ) : (
               <Sider
                  trigger={null}
                  collapsible
                  collapsed={sideMenuCollapsed}
                  width={LAYOUT.SIDER_WIDTH}
                  collapsedWidth={LAYOUT.SIDER_COLLAPSED_WIDTH}
                  style={{
                     overflow: "auto",
                     position: "fixed",
                     left: 0,
                     top: showDesktopHeader ? LAYOUT.HEADER_HEIGHT : 0,
                     bottom: 0,
                     borderRight: `1px solid ${token.colorBorder}`,
                     background: token.colorBgElevated,
                     boxShadow: sideMenuCollapsed
                        ? "none"
                        : "2px 0 8px rgba(0,0,0,0.06)"
                  }}
               >
                  {sidebarContent}
               </Sider>
            )}

            <Layout
               style={{
                  marginLeft: isSmallScreen
                     ? 0
                     : sideMenuCollapsed
                       ? LAYOUT.SIDER_COLLAPSED_WIDTH
                       : LAYOUT.SIDER_WIDTH,
                  minHeight: viewportHeight,
                  height: fullHeight ? viewportHeight : "auto",
                  transition: "all 0.2s ease",
                  background: token.colorBgContainer,
                  display: "flex",
                  flexDirection: "column",
                  overflow: fullHeight ? "hidden" : "visible"
               }}
            >
               <Content
                  key={location.pathname}
                  className="page-content-transition"
                  style={{
                     ["--app-chrome-row-height" as string]: `${LAYOUT.HEADER_HEIGHT}px`,
                     ["--app-shell-content-padding" as string]:
                        typeof resolvedContentPadding === "number"
                           ? `${resolvedContentPadding}px`
                           : String(resolvedContentPadding),
                     ["--app-page-content-padding" as string]: `${resolvedPagePadding}px`,
                     margin: centerContent ? "0 auto" : "0",
                     padding: resolvedContentPadding,
                     maxWidth: centerContent ? maxWidth : "none",
                     width: "100%",
                     background: token.colorBgContainer,
                     flex: 1,
                     display: "flex",
                     flexDirection: "column",
                     overflow: fullHeight ? "hidden" : "visible",
                     minHeight: 0
                  }}
               >
                  <PageErrorBoundary>
                     <Outlet />
                  </PageErrorBoundary>
               </Content>
               {!fullHeight && (footer ?? <AppFooter />)}
            </Layout>
         </Layout>
      </Layout>
   );
};

export default AppShellLayout;
