import { useProject } from "@kontext-tech/project";
import { useRoute } from "@/hooks/useRoute";
import type { MenuItem } from "@/utils/menuUtils";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Menu } from "antd";
import React, { useMemo } from "react";

interface SideMenuProps {
   collapsed?: boolean;
   isDarkMode: boolean;
   items: MenuItem[];
   isLoading?: boolean;
   defaultOpenKeys?: string[];
   selectedKeys?: string[];
   openKeys?: string[];
   onOpenChange?: (openKeys: string[]) => void;
}

/**
 * A reusable side menu component that can be used for both user and project navigation
 */
const SideMenu: React.FC<SideMenuProps> = ({
   collapsed = false,
   isDarkMode,
   items,
   isLoading = false,
   defaultOpenKeys,
   selectedKeys: overrideSelectedKeys,
   openKeys,
   onOpenChange
}) => {
   const { currentRoute, getRouteInstanceKey } = useRoute();
   const { currentProject } = useProject();

   const selectedKey = useMemo(() => {
      // Use override if provided
      if (overrideSelectedKeys) {
         return overrideSelectedKeys;
      }

      if (currentRoute) {
         const keys = getRouteInstanceKey(currentRoute, currentProject);
         return keys ? [keys] : [];
      }
      return [];
   }, [
      currentRoute,
      getRouteInstanceKey,
      currentProject,
      overrideSelectedKeys
   ]);

   if (isLoading) {
      return <LoadingSpinner />;
   }

   return (
      <Menu
         theme={isDarkMode ? "dark" : "light"}
         mode="inline"
         selectedKeys={selectedKey}
         items={items}
         inlineCollapsed={collapsed}
         defaultOpenKeys={defaultOpenKeys}
         openKeys={openKeys}
         onOpenChange={onOpenChange}
      />
   );
};

export default SideMenu;
