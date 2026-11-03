import PageContainer from "@/components/layout/SeoPageContainer";
import { usePermissionContext } from "@/context/AppPermissionContext";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import type { ProjectRole } from "@kontext-labs/auth";
import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import { ArrowRightOutlined, PlusOutlined } from "@kontext-labs/icons";
import { getHelpLinks } from "@kontext-labs/layout";
import { useUser } from "@kontext-labs/identity";
import {
   ProjectCreateModal,
   ProjectFilters,
   ProjectListItem,
   useProject,
   useProjectListing
} from "@kontext-labs/project";
import { SiteFeature, type ProjectModel } from "@kontext-labs/schema";
import { useSiteConfigStore } from "@kontext-labs/site";
import { useUiApp } from "@kontext-labs/ui";
import {
   Affix,
   Button,
   Card,
   Col,
   Empty,
   Flex,
   Grid,
   Pagination,
   Row,
   Space,
   theme,
   Typography
} from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const { Title, Text } = Typography;

const HomePage = () => {
   const navigate = useNavigate();
   const { user, getUserRolesForProject } = useUser();
   const apiErrorHandler = useApiErrorHandler();
   const { message } = useUiApp();
   const { getProjectChatPath, getProjectHomePath, getProjectSettingsPath } =
      useRoute();
   const { isProjectAdmin } = usePermissionContext();
   const { token } = theme.useToken();
   const { currentProject, setCurrentProject } = useProject();
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const isLocalMode =
      siteConfig?.features?.includes(SiteFeature.LOCAL_MODE) ?? false;
   const [showCreateModal, setShowCreateModal] = useState(false);

   const {
      projects,
      isLoading,
      totalCount,
      pageIndex,
      pageSize,
      searchText,
      roleFilters,
      setPageIndex,
      setPageSize,
      setSearchText,
      setRoleFilters,
      resetFilters
   } = useProjectListing(
      {
         initialPageSize: 10,
         initialIncludePublic: false,
         includePrivate: true
      },
      apiErrorHandler
   );

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

   // Opening a project sets it as the current project and navigates in one
   // step, removing the previous "select then navigate" friction.
   const openProject = (project: ProjectModel) => {
      setCurrentProject(project);
      navigate(getProjectHomePath(project));
   };

   const openProjectChat = (project: ProjectModel) => {
      setCurrentProject(project);
      navigate(getProjectChatPath(project));
   };

   const openProjectSettings = (project: ProjectModel) => {
      setCurrentProject(project);
      navigate(getProjectSettingsPath(project));
   };

   const handleProjectCreated = (project?: ProjectModel) => {
      setShowCreateModal(false);
      if (project) {
         setCurrentProject(project);
         navigate(getProjectHomePath(project));
      }
   };

   const renderProjectList = () => {
      if (projects.length === 0 && !isLoading) {
         return (
            <Card size="small">
               <Empty description="No projects found" />
            </Card>
         );
      }

      return (
         <Card size="small">
            <Flex vertical gap="small">
               {isLoading ? (
                  <div style={{ padding: "40px 0", textAlign: "center" }}>
                     Loading...
                  </div>
               ) : (
                  projects.map((project) => (
                     <ProjectListItem
                        key={project.id}
                        project={project}
                        isCurrentProject={currentProject?.id === project.id}
                        onSelect={openProject}
                        onOpenProject={openProject}
                        onOpenChat={openProjectChat}
                        onOpenSettings={() => openProjectSettings(project)}
                        projectRoles={
                           getUserRolesForProject(project.id) as ProjectRole[]
                        }
                        canOpenSettings={isProjectAdmin(project)}
                        showSelect={false}
                     />
                  ))
               )}
            </Flex>
         </Card>
      );
   };

   const renderFilters = () => {
      const filtersComponent = (
         <ProjectFilters
            roleFilters={roleFilters}
            searchText={searchText}
            onRoleFilterChange={handleRoleFilterChange}
            onResetFilters={resetFilters}
            onSearch={handleSearch}
            showSearch={true}
            showPublicToggle={false}
            showRoleFilter={true}
         />
      );

      if (screens.md) {
         return (
            <Affix offsetTop={72}>
               <div>{filtersComponent}</div>
            </Affix>
         );
      }

      return filtersComponent;
   };

   const renderGettingStarted = () => (
      <Card title="Getting Started" styles={{ body: { padding: 0 } }}>
         <div
            style={{
               position: "relative",
               paddingBottom: "56.25%",
               height: 0,
               overflow: "hidden",
               borderBottomLeftRadius: token.borderRadiusLG,
               borderBottomRightRadius: token.borderRadiusLG
            }}
         >
            <iframe
               src="https://www.youtube.com/embed/0veAg83sCvE"
               title="Kontext Demo"
               style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  border: 0
               }}
               allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
               allowFullScreen
            />
         </div>
      </Card>
   );

   const helpLinks = getHelpLinks();

   const renderHelpResources = () => (
      <Flex vertical gap="large" style={{ width: "100%" }}>
         <Text
            strong
            style={{
               fontSize: 16,
               letterSpacing: 0.2,
               color: token.colorTextHeading
            }}
         >
            Help & Resources
         </Text>

         <Flex vertical gap="small">
            {helpLinks.map((link) => (
               <a
                  key={link.key}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: "none" }}
               >
                  <Card
                     hoverable
                     size="small"
                     styles={{
                        body: {
                           display: "flex",
                           alignItems: "center",
                           gap: 12,
                           padding: "12px 16px"
                        }
                     }}
                  >
                     <Flex
                        align="center"
                        justify="center"
                        style={{
                           width: 36,
                           height: 36,
                           flex: "0 0 auto",
                           borderRadius: token.borderRadiusLG,
                           background: token.colorPrimaryBg,
                           color: token.colorPrimary,
                           fontSize: 16
                        }}
                     >
                        {link.icon}
                     </Flex>
                     <Flex vertical gap={2} style={{ flex: 1, minWidth: 0 }}>
                        <Flex align="center" gap={6}>
                           <Text strong>{link.label}</Text>
                           <ArrowRightOutlined
                              style={{
                                 fontSize: 12,
                                 color: token.colorTextTertiary
                              }}
                           />
                        </Flex>
                        {link.description && (
                           <Text
                              type="secondary"
                              style={{
                                 fontSize: 12,
                                 lineHeight: 1.45
                              }}
                           >
                              {link.description}
                           </Text>
                        )}
                     </Flex>
                  </Card>
               </a>
            ))}
         </Flex>
      </Flex>
   );

   return (
      <>
         <PageContainer
            key={`home-${user?.id || "guest"}`}
            title="Home"
            description="Browse projects, chat with your data, and manage your account."
            routeName={RouteNames.HOME}
            type="website"
            showBreadcrumb={false}
            showPageTitle={false}
         >
            <Space
               orientation="vertical"
               style={{ width: "100%" }}
               size="large"
            >
               {/* Header */}
               <Flex
                  justify="space-between"
                  align="center"
                  wrap="wrap"
                  gap="middle"
               >
                  <div>
                     <Title level={1} style={{ marginBottom: "8px" }}>
                        {`Hello, ${user?.firstName}`}
                     </Title>
                     <Text type="secondary" style={{ fontSize: "16px" }}>
                        Pick a project to start chatting with your data and
                        generating AI-powered insights.
                     </Text>
                  </div>
                  <Button
                     type="primary"
                     icon={<PlusOutlined />}
                     disabled={!isLocalMode}
                     shape="round"
                     onClick={() => setShowCreateModal(true)}
                  >
                     Create Project
                  </Button>
               </Flex>

               <Row gutter={[24, 24]}>
                  {/* Sidebar with filters */}
                  <Col xs={24} md={8} lg={7}>
                     {renderFilters()}
                  </Col>

                  {/* Main content */}
                  <Col xs={24} md={16} lg={12}>
                     <Flex vertical gap="large" style={{ width: "100%" }}>
                        {renderProjectList()}

                        {/* Pagination */}
                        {totalCount > 0 && (
                           <Flex justify="end">
                              <Pagination
                                 current={pageIndex}
                                 pageSize={pageSize}
                                 total={totalCount}
                                 showSizeChanger
                                 pageSizeOptions={PAGE_SIZE_OPTIONS}
                                 onChange={handlePageChange}
                                 onShowSizeChange={(current, size) =>
                                    handlePageChange(current, size)
                                 }
                              />
                           </Flex>
                        )}

                        {/* Getting Started */}
                        {projects.length === 0 &&
                           !isLoading &&
                           renderGettingStarted()}
                     </Flex>
                  </Col>

                  {/* Help & Resources sidebar */}
                  <Col xs={24} md={24} lg={5}>
                     {renderHelpResources()}
                  </Col>
               </Row>
            </Space>
         </PageContainer>

         <ProjectCreateModal
            open={showCreateModal}
            onCancel={() => setShowCreateModal(false)}
            onSuccess={handleProjectCreated}
            errorHandler={apiErrorHandler}
            notifySuccess={(content) => message.success(content)}
            notifyError={(content) => message.error(content)}
            defaultAccessLevel="Private"
            showAccessLevel={false}
         />
      </>
   );
};

export default HomePage;
