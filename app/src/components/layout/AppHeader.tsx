import ProjectSelectorLazy from "@/shell/project/ProjectSelectorLazy";
import { useProject } from "@kontext-tech/project";
import { useUser } from "@kontext-tech/identity";
import { getAppUrl } from "@kontext-tech/common/utils";
import { MenuOutlined, QuestionCircleOutlined } from "@kontext-tech/icons";
import { getHelpMenuItems } from "@kontext-tech/layout";
import { ThemeSelector } from "@kontext-tech/theme";
import { Button, Dropdown, Flex, Layout, theme } from "antd";
import { Suspense } from "react";
import UserNav from "./UserNav";

const { Header } = Layout;

interface AppHeaderProps {
   collapsed: boolean;
   setCollapsed: (collapsed: boolean) => void;
   isSmallScreen?: boolean;
   toggleDrawer?: () => void;
   siteLogo: string;
   smallLogo?: string;
   showProjectSelector?: boolean;
}

const AppHeader = ({
   collapsed,
   setCollapsed,
   isSmallScreen = false,
   toggleDrawer = () => {},
   siteLogo,
   smallLogo,
   showProjectSelector = false
}: AppHeaderProps) => {
   const { useToken } = theme;
   const { token } = useToken();
   const { isAuthenticated, user } = useUser();
   const { currentProject } = useProject();

   const helpMenuItems = getHelpMenuItems() ?? [];

   return (
      <>
         <Header
            style={{
               padding: "0 16px",
               background: token.colorBgContainer,
               position: "sticky",
               top: 0,
               zIndex: 1000,
               display: "flex",
               alignItems: "center",
               width: "100%",
               height: 56, // Explicitly set height to match LAYOUT.HEADER_HEIGHT
               borderBottom: `1px solid ${token.colorBorder}`,
               boxShadow: "0 2px 8px rgba(0,0,0,0.06)"
            }}
         >
            {isSmallScreen ? (
               <Button
                  type="text"
                  icon={<MenuOutlined />}
                  aria-label="Open navigation drawer"
                  onClick={toggleDrawer}
               />
            ) : (
               <Button
                  type="text"
                  icon={<MenuOutlined />}
                  aria-label="Toggle navigation menu"
                  onClick={() => setCollapsed(!collapsed)}
               />
            )}

            <a
               href={getAppUrl()}
               style={{
                  display: "flex",
                  alignItems: "center",
                  marginRight: "16px"
               }}
            >
               <img
                  src={
                     isSmallScreen
                        ? (smallLogo ?? siteLogo)
                        : collapsed && smallLogo
                          ? smallLogo
                          : siteLogo
                  }
                  alt="logo"
                  style={{
                     width: isSmallScreen
                        ? "32px"
                        : collapsed && smallLogo
                          ? "32px"
                          : "180px",
                     height: "auto",
                     marginLeft: "8px"
                  }}
               />
            </a>

            {/* Project Selector - only show when explicitly enabled */}
            {currentProject && !isSmallScreen && showProjectSelector && (
               <Suspense fallback={null}>
                  <ProjectSelectorLazy />
               </Suspense>
            )}

            <Flex align="center" gap="small" style={{ marginLeft: "auto" }}>
               <Dropdown menu={{ items: helpMenuItems }} trigger={["click"]}>
                  <Button
                     type="text"
                     icon={<QuestionCircleOutlined />}
                     aria-label="Open help menu"
                     style={{ cursor: "pointer" }}
                  />
               </Dropdown>
               <ThemeSelector />
               <UserNav
                  key={`${isAuthenticated}-${user?.id || "anonymous"}`}
                  includeNavigationItems={false}
               />
            </Flex>
         </Header>
      </>
   );
};

export default AppHeader;
