import { useLogoutAction } from "@/hooks/useLogoutAction";
import { useRoute } from "@/hooks/useRoute";
import { SignInButton } from "@kontext-labs/auth";
import { UserAvatar, useUser } from "@kontext-labs/identity";
import { RouteNames } from "@/types";
import { getUserMenuItems } from "@/utils/menuUtils";
import { useSiteConfigStore } from "@kontext-labs/site";
import { HomeOutlined, LogoutOutlined } from "@kontext-labs/icons";
import { Button, Dropdown, Space } from "antd";
import { useNavigate } from "react-router-dom";

interface UserNavProps {
   includeNavigationItems?: boolean;
}

const UserNav = ({ includeNavigationItems = true }: UserNavProps) => {
   const { user, isAuthenticated, clearStore } = useUser();
   const navigate = useNavigate();
   const { getRoutePath } = useRoute();
   const handleLogoff = useLogoutAction();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);

   // For authenticated users, show their profile dropdown
   if (isAuthenticated && user) {
      const userMenuItems = includeNavigationItems
         ? getUserMenuItems(navigate, siteConfig)
         : [];

      // Add user name and logout button
      userMenuItems.unshift({
         key: "user-name",
         label: (
            <span>
               {[user.firstName, user.lastName].filter(Boolean).join(" ")}
            </span>
         )
      });

      // The header dropdown suppresses the standard navigation items, so add a
      // direct link back to the User Console (HOME) when they are not present.
      if (!includeNavigationItems) {
         userMenuItems.push({
            key: "user-console",
            icon: <HomeOutlined />,
            label: "User Console",
            onClick: () => navigate(getRoutePath(RouteNames.HOME))
         });
      }

      userMenuItems.push({
         key: "logout",
         label: (
            <Button
               icon={<LogoutOutlined />}
               type="link"
               onClick={handleLogoff}
            >
               Logout
            </Button>
         )
      });

      return (
         <Dropdown menu={{ items: userMenuItems }} trigger={["click"]}>
            <div style={{ cursor: "pointer" }}>
               <UserAvatar user={user} size="large" />
            </div>
         </Dropdown>
      );
   }

   // For anonymous users, show login button and home link
   return (
      <Space>
         <SignInButton
            loginPath={getRoutePath(RouteNames.LOGIN)}
            includeReturnUrl
            onBeforeNavigate={clearStore}
            onNavigate={(href) => navigate(href)}
         />
      </Space>
   );
};

export default UserNav;
