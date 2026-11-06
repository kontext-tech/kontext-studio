import PageContainer from "@/components/layout/SeoPageContainer";
import { usePermissionContext } from "@/context/AppPermissionContext";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import {
   PROJECT_ROLE_FILTER_OPTIONS,
   type ProjectRole
} from "@kontext-labs/auth";
import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import {
   ArrowRightOutlined,
   CheckCircleOutlined,
   CodeOutlined,
   ExclamationCircleOutlined,
   MessageOutlined,
   PlusOutlined,
   SparklesOutlined
} from "@kontext-labs/icons";
import { getHelpLinks } from "@kontext-labs/layout";
import { useUser } from "@kontext-labs/identity";
import {
   ProjectCreateModal,
   useProject,
   useProjectListing
} from "@kontext-labs/project";
import { SiteFeature, type ProjectModel } from "@kontext-labs/schema";
import { useSiteConfigStore } from "@kontext-labs/site";
import { useTheme } from "@kontext-labs/theme";
import { DebouncedSearch, useUiApp } from "@kontext-labs/ui";
import {
   Button,
   Flex,
   Modal,
   Pagination,
   Select,
   Skeleton,
   Space,
   Typography,
   theme
} from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { useMemo, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import HomeProjectCard from "../components/HomeProjectCard";
import {
   useRecentChats,
   useWorkspaceReadiness,
   type ReadinessItem
} from "../hooks/useHomeData";

dayjs.extend(relativeTime);

const { Text } = Typography;

const HomePage = () => {
   const navigate = useNavigate();
   const { user, getUserRolesForProject } = useUser();
   const apiErrorHandler = useApiErrorHandler();
   const { message } = useUiApp();
   const {
      getGeneralRoutePath,
      getProjectChatPath,
      getProjectChatSessionDetailPath,
      getProjectHomePath,
      getProjectSettingsPath
   } = useRoute();
   const { isProjectAdmin } = usePermissionContext();
   const { token } = theme.useToken();
   const { isDarkMode } = useTheme();
   const { setCurrentProject } = useProject();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const isLocalMode =
      siteConfig?.features?.includes(SiteFeature.LOCAL_MODE) ?? false;
   const [showCreateModal, setShowCreateModal] = useState(false);
   const [showDemoModal, setShowDemoModal] = useState(false);

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
         initialPageSize: 9,
         initialIncludePublic: false,
         includePrivate: true
      },
      apiErrorHandler
   );

   const { recentChats } = useRecentChats(projects);
   const {
      items: readinessItems,
      needsSetup,
      modelLabel,
      pythonLabel
   } = useWorkspaceReadiness();

   const homeStyle = useMemo(
      () =>
         ({
            "--home-surface": token.colorBgContainer,
            "--home-border": token.colorBorderSecondary,
            "--home-accent": token.colorPrimary,
            "--home-accent-soft": token.colorPrimaryBg,
            "--home-accent-border": token.colorPrimaryBorder,
            "--home-fill-soft": token.colorFillQuaternary,
            "--home-text": token.colorText,
            "--home-muted": token.colorTextSecondary,
            "--home-muted-soft": token.colorTextTertiary,
            "--home-shadow": isDarkMode
               ? "0 10px 30px rgba(0, 0, 0, 0.45)"
               : "0 10px 30px rgba(15, 23, 42, 0.10)"
         }) as CSSProperties,
      [token, isDarkMode]
   );

   const gradientStyle = {
      ["--gradient-start"]: token.colorPrimary,
      ["--gradient-end"]: token.colorInfo
   } as CSSProperties;

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

   const openChatSession = (
      sessionId: string,
      sessionName: string,
      project: ProjectModel
   ) => {
      setCurrentProject(project);
      navigate(
         getProjectChatSessionDetailPath(project, sessionId, sessionName)
      );
   };

   const handleProjectCreated = (project?: ProjectModel) => {
      setShowCreateModal(false);
      if (project) {
         setCurrentProject(project);
         navigate(getProjectHomePath(project));
      }
   };

   const firstName = user?.firstName?.trim();
   const hasPersonalName =
      Boolean(firstName) && firstName?.toLowerCase() !== "local";
   const displayName = hasPersonalName ? firstName : undefined;
   const hasActiveFilters =
      searchText.length > 0 || (roleFilters?.length ?? 0) > 0;
   const projectCountLabel = `${totalCount} ${
      totalCount === 1 ? "project" : "projects"
   }`;
   const showRoleFilter = totalCount > 0;

   const setupActions: Record<string, { label: string; path: string }> = {
      model: {
         label: "Connect a model",
         path: getGeneralRoutePath(RouteNames.USER_MODEL_CONNECTIONS)
      },
      python: {
         label: "Prepare runtime",
         path: getGeneralRoutePath(RouteNames.USER_PYTHON_ENVIRONMENT)
      }
   };

   const renderReadinessItem = (item: ReadinessItem) => {
      const action = setupActions[item.key];
      const isReady = item.state === "ready";

      return (
         <div className="home-setup__item" key={item.key}>
            <span className="home-setup__icon">
               {isReady ? (
                  <CheckCircleOutlined style={{ color: token.colorSuccess }} />
               ) : (
                  <ExclamationCircleOutlined
                     style={{ color: token.colorWarning }}
                  />
               )}
            </span>
            <div className="home-setup__copy">
               <Text strong>{item.title}</Text>
               <Text type="secondary">{item.detail}</Text>
            </div>
            {!isReady && action && item.state === "missing" && (
               <Button
                  size="small"
                  type="link"
                  onClick={() => navigate(action.path)}
               >
                  {action.label}
               </Button>
            )}
         </div>
      );
   };

   const renderHero = () => (
      <section className="home-hero">
         <div className="home-hero__copy">
            <span className="home-eyebrow">
               {isLocalMode ? "Local workspace" : "Workspace"}
            </span>
            <h1 className="home-title">
               {displayName ? (
                  <>
                     Hello,{" "}
                     <span className="gradient-text" style={gradientStyle}>
                        {displayName}
                     </span>
                  </>
               ) : (
                  "Welcome back"
               )}
            </h1>
            <p className="home-subtitle">
               Ask your data, build notebooks, and keep the answers that matter.
            </p>
            <div className="home-hero__status">
               {!hasActiveFilters && (
                  <span className="home-status-chip">{projectCountLabel}</span>
               )}
               {modelLabel && (
                  <span className="home-status-chip">
                     <SparklesOutlined />
                     {modelLabel}
                  </span>
               )}
               {pythonLabel && (
                  <span className="home-status-chip">
                     <CodeOutlined />
                     {pythonLabel}
                  </span>
               )}
            </div>
         </div>
         <Flex className="home-hero__actions" gap="small" wrap>
            <Button
               type="primary"
               icon={<PlusOutlined />}
               disabled={!isLocalMode}
               onClick={() => setShowCreateModal(true)}
            >
               Create Project
            </Button>
         </Flex>
      </section>
   );

   const renderSetup = () =>
      needsSetup && readinessItems.length > 0 ? (
         <section className="home-setup" aria-label="Workspace setup">
            <div className="home-setup__intro">
               <span className="home-setup__badge">Setup</span>
               <Text strong>Finish setting up your workspace</Text>
               <Text type="secondary">
                  Complete these steps so chats and Python blocks are ready to
                  run.
               </Text>
            </div>
            <div className="home-setup__items">
               {readinessItems.map(renderReadinessItem)}
            </div>
         </section>
      ) : null;

   const renderRecentChats = () =>
      recentChats.length > 0 ? (
         <section className="home-section">
            <div className="home-section__head">
               <div>
                  <h2 className="home-section__title">
                     Pick up where you left off
                  </h2>
                  <span className="home-section__sub">
                     Recent conversations across your projects.
                  </span>
               </div>
            </div>
            <div className="home-recent-grid">
               {recentChats.map(({ session, project }) => (
                  <a
                     key={session.id}
                     className="home-recent-card"
                     href={getProjectChatSessionDetailPath(
                        project,
                        session.id,
                        session.sessionName
                     )}
                     onClick={(event) => {
                        event.preventDefault();
                        openChatSession(
                           session.id,
                           session.sessionName,
                           project
                        );
                     }}
                  >
                     <span className="home-recent-card__icon">
                        <MessageOutlined />
                     </span>
                     <span className="home-recent-card__body">
                        <span className="home-recent-card__title">
                           {session.sessionName || "Untitled chat"}
                        </span>
                        <span className="home-recent-card__meta">
                           {project.projectName} ·{" "}
                           {dayjs(
                              session.dateModified ?? session.dateCreated
                           ).fromNow()}
                        </span>
                     </span>
                     <ArrowRightOutlined className="home-recent-card__arrow" />
                  </a>
               ))}
            </div>
         </section>
      ) : null;

   const renderProjects = () => (
      <section className="home-section">
         <div className="home-section__head">
            <div>
               <h2 className="home-section__title">Projects</h2>
               <span className="home-section__sub">
                  {hasActiveFilters
                     ? `${totalCount} matching ${
                          totalCount === 1 ? "project" : "projects"
                       }`
                     : `${totalCount} ${
                          totalCount === 1 ? "project" : "projects"
                       } in this workspace`}
               </span>
            </div>
            <div className="home-toolbar">
               <DebouncedSearch
                  key={searchText}
                  placeholder="Search projects..."
                  allowClear
                  defaultValue={searchText}
                  onSearch={handleSearch}
                  style={{ width: 240 }}
               />
               {showRoleFilter && (
                  <Select
                     mode="multiple"
                     allowClear
                     placeholder="Filter by role"
                     value={roleFilters || []}
                     onChange={handleRoleFilterChange}
                     options={PROJECT_ROLE_FILTER_OPTIONS}
                     style={{ minWidth: 180 }}
                  />
               )}
               {hasActiveFilters && (
                  <Button type="link" size="small" onClick={resetFilters}>
                     Clear
                  </Button>
               )}
            </div>
         </div>

         {isLoading ? (
            <div className="home-project-grid">
               {[0, 1, 2].map((index) => (
                  <div className="home-project-card" key={index}>
                     <Skeleton active paragraph={{ rows: 3 }} />
                  </div>
               ))}
            </div>
         ) : projects.length === 0 ? (
            <div className="home-empty">
               <span className="home-empty__icon">
                  <SparklesOutlined />
               </span>
               <h3 className="home-empty__title">
                  {hasActiveFilters
                     ? "No projects match those filters"
                     : "Create your first project"}
               </h3>
               <p className="home-empty__copy">
                  {hasActiveFilters
                     ? "Clear the search and role filters to see every project."
                     : "A project holds your data sources, files, chats, and the notebooks the agent builds for you."}
               </p>
               <Space wrap>
                  {hasActiveFilters ? (
                     <Button onClick={resetFilters}>Clear filters</Button>
                  ) : (
                     <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        disabled={!isLocalMode}
                        onClick={() => setShowCreateModal(true)}
                     >
                        Create Project
                     </Button>
                  )}
                  <Button onClick={() => setShowDemoModal(true)}>
                     Watch the 2-minute demo
                  </Button>
               </Space>
               {!hasActiveFilters && (
                  <div className="home-empty__steps">
                     <span>1. Create a project</span>
                     <span>2. Connect a data source</span>
                     <span>3. Ask a question</span>
                  </div>
               )}
            </div>
         ) : (
            <div className="home-project-grid">
               {projects.map((project) => (
                  <HomeProjectCard
                     key={project.id}
                     project={project}
                     projectRoles={
                        getUserRolesForProject(project.id) as ProjectRole[]
                     }
                     canOpenSettings={isProjectAdmin(project)}
                     onOpenProject={openProject}
                     onOpenChat={openProjectChat}
                     onOpenSettings={openProjectSettings}
                  />
               ))}
               {isLocalMode && (
                  <button
                     type="button"
                     className="home-project-card home-project-card--new"
                     onClick={() => setShowCreateModal(true)}
                  >
                     <span className="home-project-card__new-icon">
                        <PlusOutlined />
                     </span>
                     <span className="home-project-card__new-title">
                        Create Project
                     </span>
                     <span className="home-project-card__new-copy">
                        Start with a local lakehouse and add your own data.
                     </span>
                  </button>
               )}
            </div>
         )}

         {totalCount > pageSize && (
            <Flex justify="flex-end" className="home-pagination">
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
      </section>
   );

   const helpLinks = getHelpLinks().filter((link) =>
      ["docs", "about", "contact"].includes(link.key)
   );

   const renderFooter = () => (
      <footer className="home-footer">
         {helpLinks.map((link) => (
            <a
               key={link.key}
               href={link.url}
               target="_blank"
               rel="noopener noreferrer"
            >
               {link.label}
            </a>
         ))}
         <button
            type="button"
            className="home-footer__button"
            onClick={() => setShowDemoModal(true)}
         >
            Watch the demo
         </button>
         <span className="home-footer__spacer" />
         <span>Kontext Labs · local-first</span>
      </footer>
   );

   return (
      <>
         <PageContainer
            key={`home-${user?.id || "guest"}`}
            title="Home"
            description="Browse projects, chat with your data, and manage your workspace."
            routeName={RouteNames.HOME}
            type="website"
            showBreadcrumb={false}
            showPageTitle={false}
            contentMaxWidth={1240}
         >
            <div className="home-page" style={homeStyle}>
               {renderHero()}
               {renderSetup()}
               {renderRecentChats()}
               {renderProjects()}
               {renderFooter()}
            </div>
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

         <Modal
            open={showDemoModal}
            onCancel={() => setShowDemoModal(false)}
            footer={null}
            width={860}
            destroyOnHidden
            title="Kontext in two minutes"
         >
            <div className="home-demo-frame">
               <iframe
                  src="https://www.youtube.com/embed/0veAg83sCvE"
                  title="Kontext demo"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
               />
            </div>
         </Modal>
      </>
   );
};

export default HomePage;
