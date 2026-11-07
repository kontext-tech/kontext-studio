import PageContainer from "@/components/layout/SeoPageContainer";
import { usePythonEnvironment } from "@/hooks/usePythonEnvironment";
import { RouteNames } from "@/types";
import { CodeOutlined, ReloadOutlined } from "@kontext-tech/icons";
import { useUiFeedback } from "@kontext-tech/ui";
import {
   Alert,
   Button,
   Card,
   Col,
   Descriptions,
   Empty,
   Flex,
   Row,
   Space,
   Spin,
   Table,
   Tabs,
   Tag,
   Typography
} from "antd";
import { useMemo } from "react";

const PythonEnvironmentPage = () => {
   const ui = useUiFeedback();
   const {
      environment,
      isLoading,
      errorMessage,
      isPreparing,
      refresh,
      prepare
   } = usePythonEnvironment();

   const handleRefresh = () => {
      void refresh();
   };

   const handlePrepare = async () => {
      try {
         await prepare();
         ui.success("Python environment prepared successfully.");
      } catch (error) {
         ui.error(
            error instanceof Error
               ? error.message
               : "Failed to prepare Python environment."
         );
      }
   };

   const packageColumns = useMemo(
      () => [
         {
            title: "Package",
            dataIndex: "name",
            key: "name",
            width: 180
         },
         {
            title: "Version",
            dataIndex: "version",
            key: "version",
            width: 140
         },
         {
            title: "Spec",
            dataIndex: "spec",
            key: "spec"
         }
      ],
      []
   );

   const actions = (
      <Space>
         <Button
            icon={<ReloadOutlined />}
            onClick={() => void handleRefresh()}
            disabled={isLoading || isPreparing}
         >
            Refresh
         </Button>
         {environment && !environment.initialized && (
            <Button
               type="primary"
               icon={<CodeOutlined />}
               loading={isPreparing}
               onClick={() => void handlePrepare()}
            >
               Prepare Environment
            </Button>
         )}
      </Space>
   );

   return (
      <PageContainer
         title="Python Environment"
         description="Inspect and prepare the Python runtime used for notebook execution."
         routeName={RouteNames.USER_PYTHON_ENVIRONMENT}
         type="website"
         showBreadcrumb={false}
         actions={actions}
         subContent={
            <Typography.Paragraph
               type="secondary"
               style={{ marginBottom: 0, maxWidth: 720 }}
            >
               View the runtime identity, Python version, and installed packages
               available to notebook execution. Preparing the environment is a
               separate, explicit action.
            </Typography.Paragraph>
         }
      >
         <Row justify="start">
            <Col xs={24} sm={24} md={22} lg={18} xl={16}>
               {isLoading ? (
                  <Flex justify="center" style={{ padding: "80px 0" }}>
                     <Spin size="large" />
                  </Flex>
               ) : !environment ? (
                  <Empty
                     description={
                        errorMessage ??
                        "Python environment details are unavailable."
                     }
                  />
               ) : (
                  <Space
                     direction="vertical"
                     size={16}
                     style={{ width: "100%" }}
                  >
                     {errorMessage && (
                        <Alert type="error" showIcon message={errorMessage} />
                     )}

                     {!environment.available && (
                        <Alert
                           type="warning"
                           showIcon
                           message="Python environment is not available in this deployment."
                        />
                     )}

                     {!environment.initialized && environment.available && (
                        <Alert
                           type="info"
                           showIcon
                           message="Environment not prepared yet"
                           description="Package details are currently shown from the configured runtime profile. Use Prepare Environment to bootstrap the managed runtime and refresh installed package versions."
                        />
                     )}

                     <Tabs
                        defaultActiveKey="details"
                        items={[
                           {
                              key: "details",
                              label: "Details",
                              children: (
                                 <Card>
                                    <Descriptions
                                       title="Runtime Details"
                                       column={2}
                                       size="small"
                                       items={[
                                          {
                                             key: "displayLabel",
                                             label: "Runtime Identity",
                                             children: environment.displayLabel
                                          },
                                          {
                                             key: "status",
                                             label: "Status",
                                             children:
                                                environment.initialized ? (
                                                   <Tag color="green">
                                                      Ready
                                                   </Tag>
                                                ) : (
                                                   <Tag color="gold">
                                                      Needs preparation
                                                   </Tag>
                                                )
                                          },
                                          {
                                             key: "backend",
                                             label: "Backend",
                                             children: environment.backend
                                          },
                                          {
                                             key: "runtimeProfile",
                                             label: "Runtime Profile",
                                             children:
                                                environment.runtimeProfile
                                          },
                                          {
                                             key: "pythonVersion",
                                             label: "Python Version",
                                             children: environment.pythonVersion
                                          },
                                          {
                                             key: "packageSource",
                                             label: "Package Source",
                                             children: (
                                                <Tag
                                                   color={
                                                      environment.packageSource ===
                                                      "installed"
                                                         ? "blue"
                                                         : "default"
                                                   }
                                                >
                                                   {environment.packageSource}
                                                </Tag>
                                             )
                                          }
                                       ]}
                                    />
                                 </Card>
                              )
                           },
                           {
                              key: "managed-packages",
                              label: "Managed Packages",
                              children: (
                                 <Card
                                    title="Managed Packages"
                                    extra={
                                       <Typography.Text type="secondary">
                                          {environment.packages.length} packages
                                       </Typography.Text>
                                    }
                                 >
                                    <Table
                                       size="small"
                                       pagination={false}
                                       rowKey="name"
                                       columns={packageColumns}
                                       dataSource={environment.packages}
                                       scroll={{ x: 560 }}
                                    />
                                 </Card>
                              )
                           }
                        ]}
                     />
                  </Space>
               )}
            </Col>
         </Row>
      </PageContainer>
   );
};

export default PythonEnvironmentPage;
