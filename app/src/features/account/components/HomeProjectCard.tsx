import { ProjectRoleTags, type ProjectRole } from "@kontext-labs/auth";
import { MessageOutlined, SettingOutlined } from "@kontext-labs/icons";
import { ProjectFeature, type ProjectModel } from "@kontext-labs/schema";
import { AccessLevelTag } from "@kontext-labs/ui";
import { Button, Tooltip, Typography, theme } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import React from "react";

dayjs.extend(relativeTime);

export interface HomeProjectCardProps {
   project: ProjectModel;
   projectRoles?: ProjectRole[];
   canOpenSettings?: boolean;
   onOpenProject: (project: ProjectModel) => void;
   onOpenChat?: (project: ProjectModel) => void;
   onOpenSettings?: (project: ProjectModel) => void;
}

const getInitials = (name: string) => {
   const parts = name.trim().split(/\s+/).filter(Boolean);
   if (parts.length === 0) {
      return "P";
   }

   return parts
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("");
};

export const HomeProjectCard: React.FC<HomeProjectCardProps> = ({
   project,
   projectRoles = [],
   canOpenSettings = false,
   onOpenProject,
   onOpenChat,
   onOpenSettings
}) => {
   const { token } = theme.useToken();
   const isChatEnabled = project.configuration?.features?.includes(
      ProjectFeature.Chat
   );
   const modifiedLabel = project.dateModified
      ? `Edited ${dayjs(project.dateModified).fromNow()}`
      : project.dateCreated
        ? `Created ${dayjs(project.dateCreated).fromNow()}`
        : "";

   const openChat = (event: React.MouseEvent) => {
      event.stopPropagation();
      if (isChatEnabled && onOpenChat) {
         onOpenChat(project);
      } else {
         onOpenProject(project);
      }
   };

   return (
      <article
         className="home-project-card"
         role="button"
         tabIndex={0}
         aria-label={`Open ${project.projectName}`}
         onClick={() => onOpenProject(project)}
         onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
               event.preventDefault();
               onOpenProject(project);
            }
         }}
      >
         <div className="home-project-card__top">
            <span className="home-project-mark" aria-hidden="true">
               {getInitials(project.projectName)}
            </span>
            <div className="home-project-card__tags">
               {project.accessLevel && (
                  <AccessLevelTag accessLevel={project.accessLevel} />
               )}
               {projectRoles.length > 0 && (
                  <ProjectRoleTags roles={projectRoles} />
               )}
            </div>
            {canOpenSettings && onOpenSettings && (
               <Tooltip title="Project settings">
                  <Button
                     type="text"
                     size="small"
                     className="home-project-card__icon"
                     icon={<SettingOutlined />}
                     aria-label={`Settings for ${project.projectName}`}
                     onClick={(event) => {
                        event.stopPropagation();
                        onOpenSettings(project);
                     }}
                  />
               </Tooltip>
            )}
         </div>

         <div className="home-project-card__body">
            <Typography.Text
               strong
               ellipsis={{ tooltip: project.projectName }}
               className="home-project-card__title"
            >
               {project.projectName}
            </Typography.Text>
            <Typography.Paragraph
               type="secondary"
               ellipsis={{
                  rows: 2,
                  tooltip: project.projectDescription || undefined
               }}
               className="home-project-card__description"
            >
               {project.projectDescription || "No description yet."}
            </Typography.Paragraph>
         </div>

         <div className="home-project-card__footer">
            <Button
               type="primary"
               size="small"
               icon={<MessageOutlined />}
               onClick={openChat}
            >
               {isChatEnabled ? "Open Chat" : "Open Project"}
            </Button>
            {modifiedLabel && (
               <span
                  className="home-project-card__meta"
                  style={{ color: token.colorTextTertiary }}
               >
                  {modifiedLabel}
               </span>
            )}
         </div>
      </article>
   );
};

export default HomeProjectCard;
