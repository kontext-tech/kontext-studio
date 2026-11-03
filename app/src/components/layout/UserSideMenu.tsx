import { getUserMenuItems } from "@/utils/menuUtils";
import { useSiteConfigStore } from "@kontext-tech/site";
import { Flex } from "antd";
import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import SideMenu from "./SideMenu";

interface UserSideMenuProps {
   collapsed: boolean;
   isDarkMode: boolean;
}

const UserSideMenu: React.FC<UserSideMenuProps> = ({
   collapsed,
   isDarkMode
}) => {
   const navigate = useNavigate();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);

   // Get menu items using the utility
   const menuItems = useMemo(
      () => getUserMenuItems(navigate, siteConfig),
      [navigate, siteConfig]
   );

   return (
      <Flex vertical style={{ height: "100%", minHeight: "100%" }}>
         <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
            <SideMenu
               collapsed={collapsed}
               isDarkMode={isDarkMode}
               items={menuItems}
            />
         </div>
      </Flex>
   );
};

export default UserSideMenu;
