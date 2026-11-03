import { usePermissionContext } from "@/context/AppPermissionContext";
import { useCanViewProjectActivity } from "@/hooks/useCanViewProjectActivity";
import { useRoute } from "@/hooks/useRoute";
import { getProjectMenuItems } from "@/utils/menuUtils";
import { useChatSessionStore } from "@kontext-tech/chat";
import { useProject } from "@kontext-tech/project";
import type { ProjectModel } from "@kontext-tech/schema";
import { Flex } from "antd";
import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import SideMenu from "./SideMenu";

interface ProjectSideMenuProps {
   collapsed: boolean;
   isDarkMode: boolean;
}

const ProjectSideMenuContent = ({
   project,
   collapsed,
   isDarkMode,
   isProjectLoading
}: {
   project: ProjectModel;
   collapsed: boolean;
   isDarkMode: boolean;
   isProjectLoading: boolean;
}) => {
   const navigate = useNavigate();
   const { chatSessionId } = useParams();
   const { currentRoute } = useRoute();
   const { hasRoutePermission } = usePermissionContext();
   const canViewActivity = useCanViewProjectActivity();

   const recentSessions = useChatSessionStore((state) => state.recentSessions);
   const totalSessions = useChatSessionStore((state) => state.totalSessions);
   const chatService = useChatSessionStore((state) => state.chatService);
   const fetchRecentSessions = useChatSessionStore(
      (state) => state.fetchRecentSessions
   );

   // Fetch recent sessions once the project store has its chat service ready
   // (the ChatSessionStoreProvider owns service initialization).
   useEffect(() => {
      if (chatService) {
         void fetchRecentSessions(true); // Always mySessionsOnly = true
      }
   }, [chatService, fetchRecentSessions]);

   const { topItems, middleItems } = useMemo(() => {
      // Create routing context for permission checks
      const routingContext = {
         project
      };

      // Get structured items from utility
      return getProjectMenuItems(
         project,
         navigate,
         hasRoutePermission,
         routingContext,
         recentSessions,
         totalSessions,
         collapsed,
         canViewActivity
      );
   }, [
      project,
      hasRoutePermission,
      navigate,
      recentSessions,
      totalSessions,
      collapsed,
      canViewActivity
   ]);

   // Determine active keys
   const selectedKeys = useMemo(() => {
      if (chatSessionId) {
         return [
            `project-${project?.projectCode}-chat-${chatSessionId}`,
            `project-${project?.projectCode}-chats`
         ];
      }

      if (currentRoute) {
         const routingContext = { project };

         // Project context-aware key resolution
         if (typeof currentRoute.key === "function") {
            const key = currentRoute.key(routingContext);
            return key ? [key] : [];
         }
         return currentRoute.key ? [currentRoute.key] : [];
      }
      return [];
   }, [chatSessionId, currentRoute, project]);

   return (
      <Flex vertical style={{ height: "100%" }}>
         {/* Top navigation items (Overview, New Chat) */}
         <div style={{ flex: "0 0 auto" }}>
            <SideMenu
               collapsed={collapsed}
               isDarkMode={isDarkMode}
               items={topItems}
               isLoading={isProjectLoading && !project}
               selectedKeys={selectedKeys}
            />
         </div>

         {/* Middle scrollable items (Chats, recent chats, work surfaces, Settings) */}
         <div
            className="project-side-menu__chat-scroll"
            style={{
               flex: "1 1 auto",
               overflowY: "auto",
               overflowX: "hidden",
               minHeight: 0
            }}
         >
            {middleItems.length > 0 && (
               <SideMenu
                  collapsed={collapsed}
                  isDarkMode={isDarkMode}
                  items={middleItems}
                  isLoading={isProjectLoading && !project}
                  selectedKeys={selectedKeys}
               />
            )}
         </div>
      </Flex>
   );
};

const ProjectSideMenu = ({ collapsed, isDarkMode }: ProjectSideMenuProps) => {
   const { currentProject, isProjectLoading, projectNotFound } = useProject();

   return (
      <Flex vertical style={{ height: "100%" }}>
         {!projectNotFound && currentProject && (
            <ProjectSideMenuContent
               project={currentProject}
               collapsed={collapsed}
               isDarkMode={isDarkMode}
               isProjectLoading={isProjectLoading}
            />
         )}

         {(projectNotFound || !currentProject) && (
            <div style={{ flex: "1 1 auto" }} />
         )}
      </Flex>
   );
};

export default ProjectSideMenu;
