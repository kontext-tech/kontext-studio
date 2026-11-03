import type { ApiErrorResult } from "@kontext-labs/common";
import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import type { ProjectRole } from "@kontext-labs/auth";
import { ArrowLeftRightOutlined, LoadingOutlined } from "@kontext-labs/icons";
import type { ProjectModel } from "@kontext-labs/schema";
import { AccessLevelTag } from "@kontext-labs/ui";
import {
   Button,
   Col,
   Empty,
   Flex,
   Grid,
   Pagination,
   Row,
   Spin,
   Tooltip,
   Typography,
   theme
} from "antd";
import type { CSSProperties } from "react";
import { useEffect } from "react";
import ProjectFilters from "../ProjectFilters";
import { useProjectListing } from "../useProjectListing";
import ProjectListItem from "./ProjectListItem";

export interface ProjectSelectorPanelProps {
   visible?: boolean;
   currentProject?: ProjectModel | null;
   onSelectProject: (project: ProjectModel) => void;
   onOpenProject?: (project: ProjectModel) => void;
   onOpenChat?: (project: ProjectModel) => void;
   onOpenSettings?: (project: ProjectModel) => void;
   getProjectRoles?: (project: ProjectModel) => ProjectRole[];
   canOpenSettings?: (project: ProjectModel) => boolean;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   loadingFallbackStyle?: CSSProperties;
   emptyDescription?: string;
}

const ProjectSelectorPanel: React.FC<ProjectSelectorPanelProps> = ({
   visible = true,
   currentProject,
   onSelectProject,
   onOpenProject,
   onOpenChat,
   onOpenSettings,
   getProjectRoles,
   canOpenSettings,
   errorHandler,
   loadingFallbackStyle,
   emptyDescription = "No projects found"
}) => {
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();

   const {
      projects,
      isLoading: isProjectsLoading,
      totalCount,
      pageIndex,
      pageSize,
      searchText,
      roleFilters,
      setPageIndex,
      setPageSize,
      setSearchText,
      setRoleFilters,
      setIncludePublic,
      resetFilters,
      loadProjects
   } = useProjectListing(
      {
         initialPageSize: 10,
         initialIncludePublic: false,
         lazy: true
      },
      errorHandler
   );

   useEffect(() => {
      if (!visible) {
         return;
      }

      setIncludePublic(false);
      loadProjects();
   }, [visible, setIncludePublic, loadProjects]);

   const handleSearch = (value: string) => {
      setSearchText(value);
      setPageIndex(1);
   };

   const handleRoleFilterChange = (values: string[]) => {
      setRoleFilters(values.length > 0 ? values : undefined);
      setPageIndex(1);
   };

   const handlePageChange = (page: number, pageSizeValue?: number) => {
      if (pageSizeValue) setPageSize(pageSizeValue);
      setPageIndex(page);
   };

   const sidebarFilters = (
      <div
         style={{
            position: screens.md ? "sticky" : "static",
            top: "20px",
            height: "fit-content"
         }}
      >
         <ProjectFilters
            roleFilters={roleFilters}
            searchText={searchText}
            onSearch={handleSearch}
            onRoleFilterChange={handleRoleFilterChange}
            onResetFilters={resetFilters}
            showSearch={true}
            showPublicToggle={false}
            showRoleFilter={true}
         />
      </div>
   );

   const renderProjectList = () => {
      if (projects.length === 0) {
         return <Empty description={emptyDescription} />;
      }

      return (
         <Flex vertical>
            {projects.map((project) => (
               <ProjectListItem
                  key={project.id}
                  project={project}
                  isCurrentProject={
                     currentProject?.projectCode === project.projectCode
                  }
                  onSelect={onSelectProject}
                  onOpenProject={onOpenProject}
                  onOpenChat={onOpenChat}
                  onOpenSettings={onOpenSettings}
                  projectRoles={getProjectRoles?.(project) ?? []}
                  canOpenSettings={canOpenSettings?.(project) ?? false}
               />
            ))}
         </Flex>
      );
   };

   if (isProjectsLoading && !currentProject) {
      return (
         <Spin
            indicator={<LoadingOutlined spin />}
            style={
               loadingFallbackStyle || {
                  padding: "16px 24px"
               }
            }
         />
      );
   }

   return (
      <Row gutter={[20, 20]}>
         <Col xs={24} md={8} lg={7}>
            {sidebarFilters}
         </Col>
         <Col xs={24} md={16} lg={17}>
            <Flex vertical style={{ width: "100%" }}>
               {renderProjectList()}
               {totalCount > 0 && (
                  <Flex justify="end" style={{ marginTop: "12px" }}>
                     <Pagination
                        current={pageIndex}
                        pageSize={pageSize}
                        total={totalCount}
                        onChange={handlePageChange}
                        showSizeChanger={false}
                        pageSizeOptions={PAGE_SIZE_OPTIONS}
                     />
                  </Flex>
               )}
            </Flex>
         </Col>
      </Row>
   );
};

export interface ProjectSelectorTriggerProps {
   currentProject?: ProjectModel | null;
   onClick: () => void;
   inSidebar?: boolean;
   collapsed?: boolean;
}

export const ProjectSelectorTrigger: React.FC<ProjectSelectorTriggerProps> = ({
   currentProject,
   onClick,
   inSidebar = false,
   collapsed = false
}) => {
   const { token } = theme.useToken();

   const getAccessLevelIcon = () => {
      if (!currentProject || !currentProject.accessLevel) return null;

      return (
         <AccessLevelTag
            accessLevel={currentProject.accessLevel}
            showIcon={false}
            showLabel={false}
            style={{ padding: 0, margin: 0 }}
         />
      );
   };

   if (inSidebar && collapsed) {
      return (
         <Tooltip placement="right" title="Switch project">
            <Button
               type="text"
               icon={<ArrowLeftRightOutlined />}
               onClick={onClick}
               aria-label="Switch project"
               style={{
                  width: "100%",
                  height: "56px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 0,
                  borderBottom: `1px solid ${token.colorBorderSecondary}`,
                  fontSize: "16px"
               }}
            />
         </Tooltip>
      );
   }

   if (inSidebar) {
      return (
         <Button
            type="text"
            onClick={onClick}
            aria-label={
               currentProject
                  ? `Switch project from ${currentProject.projectName}`
                  : "Select project"
            }
            style={{
               width: "100%",
               height: "56px",
               padding: "10px 14px",
               display: "block",
               textAlign: "left",
               borderRadius: 0,
               borderBottom: `1px solid ${token.colorBorderSecondary}`,
               position: "relative"
            }}
         >
            <Flex
               align="center"
               justify="space-between"
               style={{ marginTop: "4px" }}
            >
               <Flex
                  align="center"
                  gap="small"
                  style={{ maxWidth: "calc(100% - 24px)" }}
               >
                  <Typography.Text
                     ellipsis={{ tooltip: currentProject?.projectName }}
                     strong
                  >
                     {currentProject
                        ? currentProject.projectName
                        : "Select Project"}
                  </Typography.Text>
               </Flex>
               <ArrowLeftRightOutlined
                  style={{
                     fontSize: "16px",
                     fontWeight: 500,
                     color: token.colorPrimary
                  }}
                  title="Switch project"
               />
            </Flex>
         </Button>
      );
   }

   return (
      <Button
         onClick={onClick}
         style={{
            maxWidth: "280px",
            display: "flex",
            alignItems: "center",
            padding: "6px 10px"
         }}
         icon={getAccessLevelIcon()}
      >
         <Flex align="center" gap="small" style={{ width: "100%" }}>
            <Typography.Text
               ellipsis={{ tooltip: currentProject?.projectName }}
               style={{
                  maxWidth: "160px",
                  fontWeight: 500,
                  display: "block"
               }}
            >
               {currentProject ? currentProject.projectName : "Select Project"}
            </Typography.Text>
         </Flex>
      </Button>
   );
};

export default ProjectSelectorPanel;
