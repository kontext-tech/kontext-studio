import {
   PROJECT_ROLE_COLORS,
   PROJECT_ROLE_FILTER_OPTIONS,
   ProjectRole
} from "../constants/ProjectRole";
import { Tag } from "antd";
import React from "react";

export interface ProjectRoleTagProps {
   role: string;
   style?: React.CSSProperties;
}

const ProjectRoleTag = ({ role, style }: ProjectRoleTagProps) => {
   const color = Object.values(ProjectRole).includes(role as ProjectRole)
      ? PROJECT_ROLE_COLORS[role as ProjectRole]
      : "default";

   const displayOption = PROJECT_ROLE_FILTER_OPTIONS.find(
      (option) => option.value === role
   );
   const displayText = displayOption
      ? displayOption.label
      : role.charAt(0).toUpperCase() + role.slice(1);

   return (
      <Tag
         color={color}
         style={{ margin: "2px", fontWeight: "normal", ...style }}
      >
         {displayText}
      </Tag>
   );
};

export default ProjectRoleTag;
