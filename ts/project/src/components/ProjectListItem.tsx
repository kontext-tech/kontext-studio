import { ProjectRoleTags, type ProjectRole } from "@kontext-labs/auth";
import { UserAvatarById } from "@kontext-labs/identity";
import {
   ArrowRightOutlined,
   CheckOutlined,
   PlusOutlined,
   SettingOutlined
} from "@kontext-labs/icons";
import { ProjectFeature, type ProjectModel } from "@kontext-labs/schema";
import { AccessLevelTag } from "@kontext-labs/ui";
import { Button, Flex, Tooltip, Typography, theme } from "antd";
import React from "react";

export interface ProjectListItemProps {
   project: ProjectModel;
   isCurrentProject: boolean;
   onSelect: (project: ProjectModel) => void;
   onOpenProject?: (project: ProjectModel) => void;
   onOpenChat?: (project: ProjectModel) => void;
   onOpenSettings?: (project: ProjectModel) => void;
   projectRoles?: ProjectRole[];
   canOpenSettings?: boolean;
   showSelect?: boolean;
}

const ProjectListItem: React.FC<ProjectListItemProps> = ({
   project,
   isCurrentProject,
   onSelect,
   onOpenProject,
   onOpenChat,
   onOpenSettings,
   projectRoles = [],
   canOpenSettings = false,
   showSelect = true
}) => {
   const { token } = theme.useToken();
   const actionButtons = [];

   const isChatEnabled = project.configuration?.features?.includes(
      ProjectFeature.Chat
   );
   if (isChatEnabled && onOpenChat) {
      actionButtons.push(
         <Tooltip key="chat" title="New Chat">
            <Button
               type="text"
               icon={<PlusOutlined />}
               style={{ color: token.colorTextSecondary }}
               onClick={(e) => {
                  e.stopPropagation();
                  onOpenChat(project);
               }}
            />
         </Tooltip>
      );
   }

   if (canOpenSettings && onOpenSettings) {
      actionButtons.push(
         <Tooltip key="settings" title="Project Settings">
            <Button
               type="text"
               icon={<SettingOutlined />}
               style={{ color: token.colorTextSecondary }}
               onClick={(e) => {
                  e.stopPropagation();
                  onOpenSettings(project);
               }}
            />
         </Tooltip>
      );
   }

   if (showSelect) {
      actionButtons.push(
         isCurrentProject ? (
            <Button
               key="current"
               type="text"
               icon={<CheckOutlined />}
               style={{ color: token.colorPrimary }}
               title="Current project"
            />
         ) : (
            <Tooltip key="select" title="Select project">
               <Button
                  type="primary"
                  ghost
                  shape="circle"
                  icon={<ArrowRightOutlined />}
                  onClick={() => onSelect(project)}
               />
            </Tooltip>
         )
      );
   }

   return (
      <Flex
         align="center"
         gap="middle"
         className="project-list-item"
         style={{
            padding: "6px 10px",
            cursor: showSelect ? "pointer" : "default",
            transition: "background-color 0.2s"
         }}
         onClick={() => showSelect && onSelect(project)}
         onMouseEnter={(e) => {
            if (showSelect) {
               e.currentTarget.style.backgroundColor = token.colorBgTextHover;
            }
         }}
         onMouseLeave={(e) => {
            if (showSelect) {
               e.currentTarget.style.backgroundColor = "transparent";
            }
         }}
      >
         {project.ownerId && (
            <UserAvatarById
               userId={project.ownerId}
               size="default"
               showTooltip
               tooltipText="Project Owner"
            />
         )}
         <Flex vertical flex={1} gap="small">
            <div>
               <Tooltip
                  title={
                     <div
                        style={{
                           maxWidth: "300px",
                           whiteSpace: "normal",
                           wordBreak: "break-word"
                        }}
                     >
                        <div style={{ marginTop: "4px" }}>
                           <strong>Code:</strong> {project.projectCode}
                        </div>
                        {project.projectDescription && (
                           <div style={{ marginTop: "4px" }}>
                              {project.projectDescription}
                           </div>
                        )}
                     </div>
                  }
                  placement="top"
               >
                  <Flex
                     align="center"
                     gap="small"
                     style={{ minWidth: 0 }}
                     onClick={(e) => {
                        e.stopPropagation();
                        if (showSelect) {
                           onSelect(project);
                        } else {
                           onOpenProject?.(project);
                        }
                     }}
                  >
                     <Typography.Text
                        className="project-title"
                        strong
                        style={{
                           cursor:
                              showSelect || onOpenProject
                                 ? "pointer"
                                 : "default",
                           color: token.colorPrimary,
                           fontSize: "15px",
                           minWidth: 0
                        }}
                        ellipsis={{
                           tooltip: false
                        }}
                     >
                        {project.projectName}
                     </Typography.Text>
                  </Flex>
               </Tooltip>
            </div>
            <Flex align="center" gap="small" wrap="wrap">
               {project.accessLevel && (
                  <AccessLevelTag accessLevel={project.accessLevel} />
               )}
               {projectRoles.length > 0 && (
                  <ProjectRoleTags roles={projectRoles} />
               )}
            </Flex>
         </Flex>
         <Flex gap="small">{actionButtons}</Flex>
      </Flex>
   );
};

export default ProjectListItem;
