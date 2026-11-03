import { Space } from "antd";
import React from "react";
import ProjectRoleTag from "./ProjectRoleTag";

export interface ProjectRoleTagsProps {
   roles: string[];
   style?: React.CSSProperties;
}

const ProjectRoleTags = ({ roles, style }: ProjectRoleTagsProps) => {
   if (!roles || roles.length === 0) {
      return null;
   }

   return (
      <Space size="small" wrap style={style}>
         {roles.map((role) => (
            <ProjectRoleTag key={role} role={role} />
         ))}
      </Space>
   );
};

export default ProjectRoleTags;
