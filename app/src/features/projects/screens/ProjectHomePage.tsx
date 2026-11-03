import PageContainer from "@/components/layout/SeoPageContainer";
import { useProject } from "@kontext-tech/project";
import {
   ProjectInfoBanner,
   ProjectMetadataPanel,
   ProjectStats
} from "@kontext-tech/project";
import { useRoute } from "@/hooks/useRoute";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { RouteNames } from "@/types";
import { CommonRoleGroups, PermissionButton } from "@kontext-tech/auth";
import { getFullUrl } from "@kontext-tech/common/utils";
import { FILE_PREFIX_QUERY_PARAM, FileUploadModal } from "@kontext-tech/file";
import {
   BarChartOutlined,
   BookOutlined,
   FileOutlined,
   NotebookOutlined,
   PlusOutlined,
   UploadOutlined
} from "@kontext-tech/icons";
import {
   Card,
   Col,
   Flex,
   type GlobalToken,
   Row,
   Space,
   Tabs,
   theme,
   Typography
} from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const { Text } = Typography;
const { useToken } = theme;

const ResourceItem = ({
   icon,
   title,
   description,
   onClick,
   token
}: {
   icon: React.ReactNode;
   title: string;
   description: string;
   onClick: () => void;
   token: GlobalToken;
}) => (
   <div
      style={{
         cursor: "pointer",
         padding: "12px",
         borderRadius: token.borderRadiusLG,
         transition: "all 0.2s ease",
         marginBottom: "4px"
      }}
      onMouseEnter={(e) =>
         (e.currentTarget.style.backgroundColor = token.colorFillTertiary)
      }
      onMouseLeave={(e) =>
         (e.currentTarget.style.backgroundColor = "transparent")
      }
      onClick={onClick}
   >
      <Flex align="center" gap="middle">
         <div
            style={{
               fontSize: 20,
               color: token.colorInfo,
               display: "flex",
               alignItems: "center",
               justifyContent: "center",
               width: 32,
               height: 32,
               backgroundColor: `${token.colorInfo}15`,
               borderRadius: "8px"
            }}
         >
            {icon}
         </div>
         <Flex vertical>
            <Text strong>{title}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
               {description}
            </Text>
         </Flex>
      </Flex>
   </div>
);

type ProjectHomePageProject = NonNullable<
   ReturnType<typeof useProject>["currentProject"]
>;

const ProjectHomePageContent = ({
   currentProject
}: {
   currentProject: ProjectHomePageProject;
}) => {
   const { token } = useToken();
   const { getProjectChatPath, getFilesOverviewPath } = useRoute();
   const navigate = useNavigate();
   const apiErrorHandler = useApiErrorHandler();

   const [isUploadModalVisible, setIsUploadModalVisible] =
      useState<boolean>(false);

   return (
      <PageContainer
         key={`project-${currentProject.id}`}
         title="Overview"
         routeName={RouteNames.PROJECT_CONSOLE}
         project={currentProject}
         showBreadcrumb={false}
         showPageTitle={false}
      >
         {/* Project Info Banner */}
         <ProjectInfoBanner
            project={currentProject}
            extra={
               <Space>
                  <PermissionButton
                     shape="round"
                     icon={<UploadOutlined />}
                     onClick={() => setIsUploadModalVisible(true)}
                     allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                     tooltipWhenDisabled="You need contributor permissions to upload files"
                  >
                     Upload Files
                  </PermissionButton>
                  <PermissionButton
                     type="primary"
                     shape="round"
                     icon={<PlusOutlined />}
                     onClick={() =>
                        navigate(getProjectChatPath(currentProject))
                     }
                     allowedProjectRoles={CommonRoleGroups.ALL_USERS}
                  >
                     New Chat
                  </PermissionButton>
               </Space>
            }
         />

         <Row gutter={[24, 24]}>
            {/* Left Column: Recent Activity & Project Details */}
            <Col xs={24} lg={16}>
               <Card
                  styles={{
                     body: { padding: "0 24px 24px 24px" }
                  }}
               >
                  <Tabs
                     defaultActiveKey={"stats"}
                     items={[
                        {
                           key: "stats",
                           label: (
                              <Space>
                                 <BarChartOutlined />
                                 Project Stats
                              </Space>
                           ),
                           children: (
                              <div style={{ marginTop: 24 }}>
                                 <ProjectStats
                                    projectId={currentProject.id}
                                    project={currentProject}
                                    errorHandler={apiErrorHandler}
                                 />
                              </div>
                           )
                        },
                        {
                           key: "details",
                           label: (
                              <Space>
                                 <BookOutlined />
                                 Project Details
                              </Space>
                           ),
                           children: (
                              <div style={{ marginTop: 24 }}>
                                 <ProjectMetadataPanel
                                    project={currentProject}
                                 />
                              </div>
                           )
                        }
                     ]}
                  />
               </Card>
            </Col>

            {/* Right Column: Stats & Resources */}
            <Col xs={24} lg={8}>
               <Flex vertical gap="large">
                  <Card title="Resources & Help">
                     <Flex vertical gap="small">
                        <ResourceItem
                           icon={<FileOutlined />}
                           title="Files"
                           description="Manage documents and assets."
                           token={token}
                           onClick={() =>
                              navigate(getFilesOverviewPath(currentProject))
                           }
                        />
                        <ResourceItem
                           icon={<NotebookOutlined />}
                           title="Notebooks"
                           description="Interactive data analysis notebooks."
                           token={token}
                           onClick={() =>
                              navigate(
                                 `${getFilesOverviewPath(
                                    currentProject
                                 )}?${FILE_PREFIX_QUERY_PARAM}=.notebooks`
                              )
                           }
                        />
                        <ResourceItem
                           icon={<BookOutlined />}
                           title="Docs"
                           description="Get Started guide."
                           token={token}
                           onClick={() =>
                              window.open(
                                 getFullUrl("docs/getting-started"),
                                 "_blank"
                              )
                           }
                        />
                     </Flex>
                  </Card>
               </Flex>
            </Col>
         </Row>

         <FileUploadModal
            visible={isUploadModalVisible}
            onClose={() => setIsUploadModalVisible(false)}
            projectId={currentProject.id}
            configuration={currentProject.configuration}
         />
      </PageContainer>
   );
};

const ProjectHomePage = () => {
   const { currentProject } = useProject();

   if (!currentProject) return null;

   return <ProjectHomePageContent currentProject={currentProject} />;
};

export default ProjectHomePage;
