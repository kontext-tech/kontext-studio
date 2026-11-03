import PageContainer from "@/components/layout/SeoPageContainer";
import { ProjectUsers } from "@kontext-labs/project";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useUiFeedback } from "@kontext-labs/ui";
import { useProject } from "@kontext-labs/project";
import { ProjectDetailsForm } from "@kontext-labs/project";
import { useUser } from "@kontext-labs/identity";
import { RouteNames } from "@/types";
import { TAB_QUERY_PARAM } from "@kontext-labs/common";
import { useIsLocalMode } from "@kontext-labs/site";
import { LockOutlined, SettingOutlined } from "@kontext-labs/icons";
import type { ProjectModel } from "@kontext-labs/schema";
import { Col, Row, Space, Tabs } from "antd";
import { useSearchParams } from "react-router-dom";

// no Typography.Text usage in current layout
const DEFAULT_TAB_PROJECT_SETTINGS_PAGE = "general";

/**
 * Project settings page that allows project owners and administrators
 * to manage project details, view project information and statistics,
 * and control access levels and other settings
 */
const ProjectSettingsPage = () => {
   const [searchParams, setSearchParams] = useSearchParams();
   const currentTab =
      searchParams.get(TAB_QUERY_PARAM) || DEFAULT_TAB_PROJECT_SETTINGS_PAGE;
   const { currentProject, setCurrentProject } = useProject();
   const apiErrorHandler = useApiErrorHandler();
   const ui = useUiFeedback();

   const { user } = useUser();
   const isLocalMode = useIsLocalMode();

   if (!currentProject) return null;

   // Handle project update from the details component
   const handleProjectUpdated = (updatedProject: ProjectModel) => {
      setCurrentProject(updatedProject);
   };

   const tabItems = [
      {
         key: "general",
         label: (
            <Space>
               <SettingOutlined />
               General
            </Space>
         ),
         children: (
            <Row gutter={[24, 24]}>
               <Col xs={24} sm={24} md={20} lg={16} xl={14}>
                  <ProjectDetailsForm
                     project={currentProject}
                     onProjectUpdated={handleProjectUpdated}
                     errorHandler={apiErrorHandler}
                     ui={ui}
                     modifiedByUserId={user?.id}
                  />
               </Col>
            </Row>
         )
      },
      {
         key: "access",
         label: (
            <Space>
               <LockOutlined />
               Access & Permissions
            </Space>
         ),
         children: (
            <Space
               orientation="vertical"
               style={{ width: "100%" }}
               size="large"
            >
               {/* Project Users component */}
               <ProjectUsers
                  projectId={currentProject.id}
                  isLocalMode={isLocalMode}
                  errorHandler={apiErrorHandler}
               />
            </Space>
         ),
         hidden: isLocalMode
      }
   ].filter((item) => !item.hidden);

   const activeTab = tabItems.some((item) => item.key === currentTab)
      ? currentTab
      : DEFAULT_TAB_PROJECT_SETTINGS_PAGE;

   return (
      <PageContainer
         key={`project-settings-${currentProject.id}-${currentTab}`}
         title="Project Settings"
         description={`Manage settings for ${currentProject.projectName}.`}
         routeName={RouteNames.PROJECT_SETTINGS}
         project={currentProject}
         type="project"
         showPageTitle={true}
      >
         <Tabs
            activeKey={activeTab}
            onChange={(key: string) =>
               setSearchParams({ [TAB_QUERY_PARAM]: key })
            }
            items={tabItems}
         />
      </PageContainer>
   );
};

export default ProjectSettingsPage;
