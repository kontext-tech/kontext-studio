import ProjectSideMenu from "@/components/layout/ProjectSideMenu";
import { ChatSessionStoreProvider } from "@kontext-labs/chat";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { useUserStore } from "@kontext-labs/identity";
import { useProject, useProjectUrlSync } from "@kontext-labs/project";
import React from "react";
import { useParams } from "react-router-dom";
import BaseLayout from "./BaseLayout";

interface MenuProps {
   collapsed: boolean;
   isDarkMode: boolean;
   smallLogo: string;
   siteLogo: string;
}

/**
 * Enhanced ProjectLayout with better UX patterns
 * - Project context in sidebar
 * - Responsive design
 * - Better visual hierarchy
 * - Improved navigation
 * - Full-width app shell with route-level fluid/full-height support for immersive views
 */
const ProjectLayout: React.FC = () => {
   const { currentRoute } = useRoute();
   const { projectCode } = useParams<{ projectCode?: string }>();
   const apiErrorHandler = useApiErrorHandler();
   const accessToken = useUserStore((state) => state.tokens?.accessToken);
   const { currentProject } = useProject();

   useProjectUrlSync(projectCode, {
      accessToken,
      errorHandler: apiErrorHandler
   });

   const isFullHeightView = React.useMemo(() => {
      return currentRoute?.fullHeight === true;
   }, [currentRoute?.fullHeight]);

   const renderSideMenu = ({ collapsed, isDarkMode }: MenuProps) => (
      <ProjectSideMenu collapsed={collapsed} isDarkMode={isDarkMode} />
   );

   return (
      <ChatSessionStoreProvider
         project={currentProject}
         errorHandler={apiErrorHandler}
      >
         <BaseLayout
            renderSideMenu={renderSideMenu}
            centerContent={false}
            maxWidth="100%"
            contentPadding={0}
            showProjectSelector={true}
            fullHeight={isFullHeightView}
         />
      </ChatSessionStoreProvider>
   );
};

export default ProjectLayout;
