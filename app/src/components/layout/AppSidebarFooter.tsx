import { useLogoutAction } from "@/hooks/useLogoutAction";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import {
   DownOutlined,
   HomeOutlined,
   LogoutOutlined,
   QuestionCircleOutlined,
   SunMoonOutlined,
   UserOutlined
} from "@kontext-tech/icons";
import { UserAvatar, useUser } from "@kontext-tech/identity";
import { SidebarFooter, getHelpMenuItems } from "@kontext-tech/layout";
import { SiteFeature } from "@kontext-tech/schema";
import { useIsLocalMode, useSiteConfigStore } from "@kontext-tech/site";
import {
   themeMenuItems as buildThemeMenuItems,
   themeModeLabel,
   useTheme
} from "@kontext-tech/theme";
import {
   Button,
   Dropdown,
   Flex,
   Tooltip,
   Typography,
   theme,
   type MenuProps
} from "antd";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

interface AppSidebarFooterProps {
   collapsed: boolean;
}

const AppSidebarFooter = ({ collapsed }: AppSidebarFooterProps) => {
   const { token } = theme.useToken();
   const navigate = useNavigate();
   const { getGeneralRoutePath } = useRoute();
   const { user } = useUser();
   const { themeMode, handleThemeModeChange } = useTheme();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const isLocalMode = useIsLocalMode();
   const helpMenuItems = getHelpMenuItems();

   const hasModelConnections =
      siteConfig?.features?.includes(SiteFeature.MODEL_CONNECTIONS) ?? false;
   const hasPythonEnvironment =
      siteConfig?.features?.includes(SiteFeature.PYTHON_ENVIRONMENT) ?? false;
   const displayName = user
      ? `${user.firstName ?? ""} ${user.lastName ?? ""}`.trim() || user.email
      : "";

   const handleLogout = useLogoutAction();

   const themeLabel = themeModeLabel(themeMode);
   const themeMenuOptions = buildThemeMenuItems(handleThemeModeChange);

   const avatarMenuItems = useMemo<MenuProps["items"]>(
      () => [
         user
            ? {
                 key: "user-summary",
                 disabled: true,
                 label: (
                    <Flex vertical gap={0} style={{ minWidth: 220 }}>
                       <Typography.Text strong>{displayName}</Typography.Text>
                       <Typography.Text type="secondary">
                          {user.email}
                       </Typography.Text>
                    </Flex>
                 )
              }
            : null,
         { type: "divider" },
         {
            key: "user-console",
            icon: <HomeOutlined />,
            label: "Home",
            onClick: () => navigate(getGeneralRoutePath(RouteNames.HOME))
         },
         ...(isLocalMode
            ? [
                 {
                    key: "account",
                    icon: <UserOutlined />,
                    label: "Account Settings",
                    onClick: () =>
                       navigate(
                          getGeneralRoutePath(RouteNames.ACCOUNT_SETTINGS)
                       )
                 }
              ]
            : []),
         ...(hasModelConnections
            ? [
                 {
                    key: "llm-providers",
                    icon: <QuestionCircleOutlined />,
                    label: "LLM Providers",
                    onClick: () =>
                       navigate(
                          getGeneralRoutePath(RouteNames.USER_MODEL_CONNECTIONS)
                       )
                 }
              ]
            : []),
         ...(hasPythonEnvironment
            ? [
                 {
                    key: "python-environment",
                    icon: <SunMoonOutlined />,
                    label: "Python Environment",
                    onClick: () =>
                       navigate(
                          getGeneralRoutePath(
                             RouteNames.USER_PYTHON_ENVIRONMENT
                          )
                       )
                 }
              ]
            : []),
         {
            key: "help",
            icon: <QuestionCircleOutlined />,
            label: "Help",
            children: helpMenuItems ?? []
         },
         {
            key: "theme",
            icon: <SunMoonOutlined />,
            label: `Theme: ${themeLabel}`,
            children: themeMenuOptions
         },
         { type: "divider" },
         {
            key: "logout",
            icon: <LogoutOutlined />,
            label: "Sign Out",
            danger: true,
            onClick: () => void handleLogout()
         }
      ],
      [
         displayName,
         getGeneralRoutePath,
         handleLogout,
         hasModelConnections,
         hasPythonEnvironment,
         helpMenuItems,
         isLocalMode,
         navigate,
         themeLabel,
         themeMenuOptions,
         user
      ]
   );

   const avatarTrigger = user ? (
      <Button
         type="text"
         title={collapsed ? "Open account menu" : undefined}
         style={{
            width: collapsed ? 48 : "100%",
            minWidth: collapsed ? 48 : undefined,
            height: collapsed ? 48 : "auto",
            padding: collapsed ? 0 : 8,
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "flex-start",
            borderRadius: 12
         }}
      >
         <Flex
            align="center"
            gap={12}
            style={{ width: collapsed ? "auto" : "100%", minWidth: 0 }}
         >
            <UserAvatar user={user} size={collapsed ? "default" : "large"} />
            {!collapsed && (
               <>
                  <Flex
                     vertical
                     style={{ minWidth: 0, flex: 1, textAlign: "left" }}
                  >
                     <Typography.Text strong ellipsis>
                        {displayName}
                     </Typography.Text>
                     <Typography.Text
                        type="secondary"
                        ellipsis
                        style={{ fontSize: 12 }}
                     >
                        {user.email}
                     </Typography.Text>
                  </Flex>
                  <DownOutlined
                     style={{
                        color: token.colorTextTertiary,
                        flex: "0 0 auto"
                     }}
                  />
               </>
            )}
         </Flex>
      </Button>
   ) : null;

   return (
      <div
         style={{
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorBgContainer
         }}
      >
         {user && avatarTrigger && (
            <div style={{ padding: collapsed ? "8px 6px" : "8px 12px 12px" }}>
               <Dropdown
                  menu={{ items: avatarMenuItems }}
                  trigger={["click"]}
                  placement="topRight"
               >
                  {collapsed ? (
                     <Tooltip placement="right" title="Open account menu">
                        <div
                           style={{
                              display: "flex",
                              justifyContent: "center"
                           }}
                        >
                           {avatarTrigger}
                        </div>
                     </Tooltip>
                  ) : (
                     <div>{avatarTrigger}</div>
                  )}
               </Dropdown>
            </div>
         )}

         <SidebarFooter collapsed={collapsed} />
      </div>
   );
};

export default AppSidebarFooter;
