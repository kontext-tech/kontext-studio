import ProjectSelectorLazy from "@/shell/project/ProjectSelectorLazy";
import { getBaseUrl } from "@kontext-labs/common/utils";
import {
   PanelLeftCloseOutlined,
   PanelLeftOpenOutlined
} from "@kontext-labs/icons";
import { Button, Flex, Tooltip, theme } from "antd";
import { Suspense } from "react";

interface AppSidebarTopProps {
   collapsed: boolean;
   isSmallScreen: boolean;
   onToggleCollapsed: () => void;
   siteLogo: string;
   smallLogo?: string;
   showProjectSelector?: boolean;
}

const AppSidebarTop = ({
   collapsed,
   isSmallScreen,
   onToggleCollapsed,
   siteLogo,
   smallLogo,
   showProjectSelector = false
}: AppSidebarTopProps) => {
   const { token } = theme.useToken();
   const logoSrc = collapsed && smallLogo ? smallLogo : siteLogo;
   const showInlineToggle = !isSmallScreen && !collapsed;
   const showCollapsedToggle = !isSmallScreen && collapsed;
   const toggleButton = !isSmallScreen ? (
      <Tooltip
         placement="bottom"
         title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
         <Button
            type="text"
            size="small"
            icon={
               collapsed ? (
                  <PanelLeftOpenOutlined />
               ) : (
                  <PanelLeftCloseOutlined />
               )
            }
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggleCollapsed}
            style={{
               width: 28,
               height: 28,
               flex: "0 0 auto"
            }}
         />
      </Tooltip>
   ) : null;

   return (
      <div style={{ background: token.colorBgContainer }}>
         <Flex
            align="center"
            justify={showInlineToggle ? "space-between" : "center"}
            style={{
               height: collapsed ? 52 : 56,
               padding: collapsed ? "0 8px" : "0 12px 0 16px",
               borderBottom: showCollapsedToggle
                  ? "none"
                  : `1px solid ${token.colorBorderSecondary}`
            }}
         >
            <a
               href={getBaseUrl()}
               style={{
                  minWidth: 0,
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: collapsed ? "center" : "flex-start"
               }}
            >
               <img
                  src={logoSrc}
                  alt="Kontext"
                  style={{
                     maxWidth: collapsed && smallLogo ? "20px" : "160px",
                     maxHeight: collapsed && smallLogo ? "20px" : "22px",
                     width: "auto",
                     height: "auto",
                     objectFit: "contain"
                  }}
               />
            </a>
            {showInlineToggle ? toggleButton : null}
         </Flex>

         {showCollapsedToggle && (
            <div
               style={{
                  display: "flex",
                  justifyContent: "center",
                  padding: showProjectSelector ? "0 0 8px" : "0 0 12px",
                  borderBottom: showProjectSelector
                     ? "none"
                     : `1px solid ${token.colorBorderSecondary}`
               }}
            >
               {toggleButton}
            </div>
         )}

         {showProjectSelector && (
            <Suspense fallback={null}>
               <ProjectSelectorLazy inSidebar={true} collapsed={collapsed} />
            </Suspense>
         )}
      </div>
   );
};

export default AppSidebarTop;
