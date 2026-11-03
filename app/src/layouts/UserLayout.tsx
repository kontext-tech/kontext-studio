import UserSideMenu from "@/components/layout/UserSideMenu";
import React from "react";
import BaseLayout from "./BaseLayout";

interface MenuProps {
   collapsed: boolean;
   isDarkMode: boolean;
   isSmallScreen: boolean;
   smallLogo: string;
   siteLogo: string;
}

const UserLayout: React.FC = () => {
   const renderSideMenu = ({ collapsed, isDarkMode }: MenuProps) => (
      <UserSideMenu collapsed={collapsed} isDarkMode={isDarkMode} />
   );

   return (
      <BaseLayout
         renderSideMenu={renderSideMenu}
         centerContent={false}
         maxWidth="100%"
         contentPadding={0}
         showProjectSelector={false}
      />
   );
};

export default UserLayout;
