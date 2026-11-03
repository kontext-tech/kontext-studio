import PageContainer from "@/components/layout/SeoPageContainer";
import ConnectionSettingsFields from "@/features/projects/components/data-sources/ConnectionSettingsFields";
import DataSourceReviewPanel from "@/features/projects/components/data-sources/DataSourceReviewPanel";
import {
   buildConnectionRequest,
   getAuthTypeLabel,
   getExecutionModeLabel,
   getFormValues,
   getProviderFields,
   type CatalogFormValues
} from "@/features/projects/components/data-sources/formConfig";
import {
   getConnectionDetailsLine,
   getLatestWarning,
   getReadinessStatus
} from "@/features/projects/components/data-sources/presentation";
import { useCatalogSyncPolling } from "@/features/projects/hooks/useCatalogSyncPolling";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { RouteNames } from "@/types";
import {
   CommonRoleGroups,
   PermissionButton,
   PermissionGate
} from "@kontext-labs/auth";
import {
   CheckCircleOutlined,
   DatabaseOutlined,
   DeleteOutlined,
   EditOutlined,
   PlusOutlined,
   ReloadOutlined,
   SyncOutlined
} from "@kontext-labs/icons";
import { CatalogService, useProject } from "@kontext-labs/project";
import { useDataService } from "@kontext-labs/app-runtime/hooks";
import type {
   CatalogConnection,
   CatalogProviderDefinition
} from "@kontext-labs/schema";
import { useUiApp } from "@kontext-labs/ui";
import {
   Alert,
   Button,
   Card,
   Col,
   Empty,
   Flex,
   Form,
   Input,
   Modal,
   Row,
   Select,
   Space,
   Steps,
   Switch,
   Tabs,
   Tag,
   Typography
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

const getSubmitFieldNames = ({
   formFields,
   hasCredentialStep,
   isEditing
}: {
   formFields: ReturnType<typeof getProviderFields>;
   hasCredentialStep: boolean;
   isEditing: boolean;
}) => [
   ...(isEditing ? [] : ["providerKind"]),
   "displayName",
   ...formFields.map((field) => field.name),
   ...(hasCredentialStep
      ? ["authType", "executionMode", "secretValue", "secretRef"]
      : [])
];

const ProjectCatalogsPage = () => {
   const { currentProject } = useProject();
   const currentProjectId = currentProject?.id;
   const apiErrorHandler = useApiErrorHandler();
   const catalogService = useDataService(CatalogService, apiErrorHandler);
   const { message, modal } = useUiApp();
   const [form] = Form.useForm<CatalogFormValues>();

   const [providers, setProviders] = useState<CatalogProviderDefinition[]>([]);
   const [connections, setConnections] = useState<CatalogConnection[]>([]);
   const [isLoading, setIsLoading] = useState(true);
   const [pageError, setPageError] = useState<string | null>(null);
   const [isModalOpen, setIsModalOpen] = useState(false);
   const [editingConnection, setEditingConnection] =
      useState<CatalogConnection | null>(null);
   const [submitting, setSubmitting] = useState(false);
   const [activeProviderKind, setActiveProviderKind] = useState("all");
   const [activeConnectionId, setActiveConnectionId] = useState<string | null>(
      null
   );
   const [modalStep, setModalStep] = useState(0);
   const [modalProviderKind, setModalProviderKind] = useState<string>("");

   const watchedValues = Form.useWatch([], form);
   const selectedProvider = useMemo(
      () =>
         providers.find(
            (provider) => provider.providerKind === modalProviderKind
         ),
      [modalProviderKind, providers]
   );
   const createableProviders = useMemo(
      () =>
         providers.filter((provider) => provider.connectionKind !== "internal"),
      [providers]
   );
   const formProvider =
      selectedProvider ||
      createableProviders.find(
         (provider) => provider.providerKind === modalProviderKind
      );
   const formFields = getProviderFields(formProvider?.providerKind);
   const hasCredentialStep = Boolean(
      formProvider?.authTypes.some((value) => value !== "none")
   );
   const hasPendingSecretValue = Boolean(watchedValues?.secretValue?.trim());
   const hasConfiguredSecret = Boolean(
      hasPendingSecretValue ||
      editingConnection?.secretConfigured ||
      editingConnection?.secretRef
   );
   const submitFieldNames = useMemo(
      () =>
         getSubmitFieldNames({
            formFields,
            hasCredentialStep,
            isEditing: Boolean(editingConnection)
         }),
      [editingConnection, formFields, hasCredentialStep]
   );
   const modalSteps = [
      {
         key: "provider",
         title: "Provider",
         description: "Choose the database type",
         fields: ["providerKind"]
      },
      {
         key: "details",
         title: "Details",
         description: "Add connection settings",
         fields: ["displayName", ...formFields.map((field) => field.name)]
      },
      ...(hasCredentialStep
         ? [
              {
                 key: "access",
                 title: "Access",
                 description: "Review auth and secrets",
                 fields: [
                    "authType",
                    "executionMode",
                    "secretValue",
                    "secretRef"
                 ]
              }
           ]
         : []),
      {
         key: "review",
         title: "Review",
         description: "Confirm before saving",
         fields: [] as string[]
      }
   ];
   const isLastModalStep = modalStep === modalSteps.length - 1;
   const providerTabs = useMemo(
      () => [
         {
            key: "all",
            label: `All Data Sources (${connections.length})`
         },
         ...providers.map((provider) => ({
            key: provider.providerKind,
            label: `${provider.displayName} (${connections.filter((connection) => connection.providerKind === provider.providerKind).length})`
         }))
      ],
      [connections, providers]
   );
   const effectiveActiveProviderKind =
      activeProviderKind === "all" ||
      providers.some((provider) => provider.providerKind === activeProviderKind)
         ? activeProviderKind
         : "all";
   const visibleConnections = useMemo(() => {
      if (effectiveActiveProviderKind === "all") {
         return connections;
      }

      return connections.filter(
         (connection) => connection.providerKind === effectiveActiveProviderKind
      );
   }, [connections, effectiveActiveProviderKind]);

   const loadCatalogData = useCallback(async () => {
      if (!currentProjectId) {
         return;
      }

      setIsLoading(true);
      setPageError(null);

      const [providersResult, connectionsResult] = await Promise.all([
         catalogService.listProviders(currentProjectId),
         catalogService.listConnections(currentProjectId)
      ]);

      if (providersResult.succeed && providersResult.data) {
         setProviders(providersResult.data);
      } else {
         setProviders([]);
      }

      if (connectionsResult.succeed && connectionsResult.data) {
         setConnections(connectionsResult.data);
      } else {
         setConnections([]);
      }

      if (!providersResult.succeed || !connectionsResult.succeed) {
         setPageError(
            providersResult.error?.title ||
               connectionsResult.error?.title ||
               "Failed to load data sources."
         );
      }

      setIsLoading(false);
   }, [catalogService, currentProjectId]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void loadCatalogData();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [loadCatalogData]);

   useCatalogSyncPolling(connections, loadCatalogData);

   const openCreateModal = () => {
      const defaultProvider = createableProviders[0];
      form.setFieldsValue(getFormValues(defaultProvider));
      setModalProviderKind(defaultProvider?.providerKind || "");
      setModalStep(0);
      setEditingConnection(null);
      setIsModalOpen(true);
   };

   const openEditModal = (connection: CatalogConnection) => {
      const provider = providers.find(
         (item) => item.providerKind === connection.providerKind
      );
      form.setFieldsValue(getFormValues(provider, connection));
      setModalProviderKind(connection.providerKind);
      setModalStep(1);
      setEditingConnection(connection);
      setIsModalOpen(true);
   };

   const closeModal = () => {
      setIsModalOpen(false);
      setModalProviderKind("");
      setModalStep(0);
      setEditingConnection(null);
      form.resetFields();
   };

   const handleProviderChange = (providerKind: string) => {
      const provider = providers.find(
         (item) => item.providerKind === providerKind
      );
      const currentValues = form.getFieldsValue();
      setModalProviderKind(providerKind);
      form.setFieldsValue({
         ...getFormValues(provider),
         displayName: currentValues.displayName || provider?.displayName || "",
         description: currentValues.description,
         enabled: currentValues.enabled ?? true,
         secretRef: undefined,
         secretValue: undefined
      });
   };

   const handleNextStep = async () => {
      try {
         const fieldsToValidate = modalSteps[modalStep]?.fields;
         if (fieldsToValidate && fieldsToValidate.length > 0) {
            await form.validateFields(fieldsToValidate);
         }
         setModalStep((current) =>
            Math.min(current + 1, modalSteps.length - 1)
         );
      } catch {
         return;
      }
   };

   const handleSubmit = async () => {
      if (!currentProject?.id || !selectedProvider) {
         return;
      }

      let values: CatalogFormValues;

      try {
         const validatedValues = await form.validateFields(submitFieldNames);
         values = {
            ...form.getFieldsValue(true),
            ...validatedValues
         } as CatalogFormValues;
      } catch (error) {
         const firstErrorField = (
            error as {
               errorFields?: Array<{ name?: Array<string | number> }>;
            }
         )?.errorFields?.[0]?.name?.[0];

         if (typeof firstErrorField === "string") {
            const stepIndex = modalSteps.findIndex((step) =>
               step.fields.includes(firstErrorField)
            );

            if (stepIndex >= 0) {
               setModalStep(stepIndex);
            }
         }

         return;
      }

      setSubmitting(true);

      try {
         const request = buildConnectionRequest(values, selectedProvider);
         const result = editingConnection?.id
            ? await catalogService.updateConnection(
                 currentProject.id,
                 editingConnection.id,
                 request
              )
            : await catalogService.createConnection(currentProject.id, request);

         if (!result.succeed) {
            message.error(
               result.error?.title || "Failed to save the data source."
            );
            return;
         }

         message.success(
            selectedProvider.connectionKind === "external"
               ? "Data source saved. Initial sync started in the background."
               : editingConnection
                 ? "Data source updated"
                 : "Data source created"
         );
         closeModal();
         await loadCatalogData();
      } catch {
         message.error("Failed to save the data source.");
      } finally {
         setSubmitting(false);
      }
   };

   const withConnectionAction = async (
      connectionId: string,
      action: () => Promise<boolean>,
      finallyMessage?: string
   ) => {
      setActiveConnectionId(connectionId);
      try {
         const success = await action();
         if (success && finallyMessage) {
            message.success(finallyMessage);
         }
         if (success) {
            await loadCatalogData();
         }
      } finally {
         setActiveConnectionId(null);
      }
   };

   const handleValidate = async (connection: CatalogConnection) => {
      if (!currentProject?.id || !connection.id) {
         return;
      }

      await withConnectionAction(connection.id, async () => {
         const result = await catalogService.validateConnection(
            currentProject.id,
            connection.id!
         );
         if (!result.succeed || !result.data) {
            message.error(
               result.error?.title || "Failed to validate data source."
            );
            return false;
         }

         const validation = result.data;
         message.info(
            validation.message ||
               validation.errorMessage ||
               `Validation ${validation.status}.`
         );
         return true;
      });
   };

   const handleSync = async (connection: CatalogConnection) => {
      if (!currentProject?.id || !connection.id) {
         return;
      }

      await withConnectionAction(connection.id, async () => {
         const result = await catalogService.syncConnection(
            currentProject.id,
            connection.id!
         );
         if (!result.succeed || !result.data) {
            message.error(result.error?.title || "Failed to sync data source.");
            return false;
         }

         message.info(
            `Sync ${result.data.status}. ${result.data.entityCount} entities refreshed.`
         );
         return true;
      });
   };

   const handleDelete = (connection: CatalogConnection) => {
      if (!currentProject?.id || !connection.id) {
         return;
      }

      modal.confirm({
         title: `Delete ${connection.displayName}?`,
         content:
            "This removes the saved data source and its synced metadata for this project.",
         okText: "Delete",
         okButtonProps: {
            danger: true
         },
         onOk: async () => {
            await withConnectionAction(
               connection.id!,
               async () => {
                  const result = await catalogService.deleteConnection(
                     currentProject.id,
                     connection.id!
                  );
                  if (!result.succeed) {
                     message.error(
                        result.error?.title || "Failed to delete data source."
                     );
                     return false;
                  }
                  return true;
               },
               "Data source deleted"
            );
         }
      });
   };

   if (!currentProject) {
      return null;
   }
   const isEditingManagedConnection =
      editingConnection?.connectionKind === "internal";

   return (
      <PageContainer
         key={`project-catalogs-${currentProject.id}`}
         title="Data Sources"
         description={`Manage data sources for ${currentProject.projectName}.`}
         routeName={RouteNames.PROJECT_CATALOGS}
         project={currentProject}
         actions={
            <Space wrap>
               <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                     void loadCatalogData();
                  }}
                  loading={isLoading}
               >
                  Refresh
               </Button>
               <PermissionButton
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={openCreateModal}
                  allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                  disabled={createableProviders.length === 0}
               >
                  New Data Source
               </PermissionButton>
            </Space>
         }
         subContent={
            <Typography.Paragraph
               type="secondary"
               style={{ marginBottom: 0, maxWidth: 760 }}
            >
               Manage the internal lakehouse and external data sources, verify
               access, and keep synced metadata ready for chat and agent
               workflows.
            </Typography.Paragraph>
         }
      >
         <Space orientation="vertical" size="large" style={{ width: "100%" }}>
            {pageError && (
               <Alert
                  type="warning"
                  showIcon
                  title="Data source page is partially unavailable"
                  description={pageError}
               />
            )}

            {providers.length > 0 ? (
               <Tabs
                  type="line"
                  activeKey={effectiveActiveProviderKind}
                  onChange={setActiveProviderKind}
                  items={providerTabs}
               />
            ) : (
               <Alert
                  type="info"
                  showIcon
                  title="No data source providers available"
                  description="This runtime does not currently expose any data source providers."
               />
            )}

            {connections.length === 0 && !isLoading ? (
               <Card>
                  <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description="No data sources configured for this project yet."
                  >
                     <PermissionGate
                        allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                     >
                        <Button type="primary" onClick={openCreateModal}>
                           Create your first data source
                        </Button>
                     </PermissionGate>
                  </Empty>
               </Card>
            ) : visibleConnections.length === 0 && !isLoading ? (
               <Card>
                  <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description="No data sources are configured for this provider yet."
                  />
               </Card>
            ) : (
               <Row gutter={[16, 16]}>
                  {visibleConnections.map((connection) => {
                     const provider = providers.find(
                        (item) => item.providerKind === connection.providerKind
                     );
                     const isBusy = activeConnectionId === connection.id;
                     const isManaged = connection.connectionKind === "internal";
                     const readinessStatus = getReadinessStatus(connection);
                     const latestWarning = getLatestWarning(connection);

                     return (
                        <Col
                           xs={24}
                           xl={12}
                           key={connection.id || connection.displayName}
                        >
                           <Card
                              size="small"
                              style={{ height: "100%" }}
                              styles={{ body: { padding: 16 } }}
                           >
                              <Space
                                 orientation="vertical"
                                 size="small"
                                 style={{ width: "100%" }}
                              >
                                 <Flex
                                    align="flex-start"
                                    justify="space-between"
                                    gap="middle"
                                 >
                                    <Flex align="flex-start" gap="small">
                                       <DatabaseOutlined />
                                       <Flex vertical gap={2}>
                                          <Typography.Text strong>
                                             {connection.displayName}
                                          </Typography.Text>
                                          <Typography.Text type="secondary">
                                             {provider?.displayName ||
                                                connection.providerKind}
                                          </Typography.Text>
                                       </Flex>
                                    </Flex>
                                    <Tag color={readinessStatus.color}>
                                       {readinessStatus.label}
                                    </Tag>
                                 </Flex>

                                 <Typography.Text type="secondary">
                                    {getConnectionDetailsLine(connection)}
                                 </Typography.Text>

                                 {latestWarning && (
                                    <Alert
                                       type="warning"
                                       showIcon
                                       title="Latest issue"
                                       description={latestWarning}
                                    />
                                 )}

                                 <Flex gap="small" wrap>
                                    <PermissionButton
                                       icon={<CheckCircleOutlined />}
                                       onClick={() => {
                                          void handleValidate(connection);
                                       }}
                                       loading={isBusy}
                                       allowedProjectRoles={
                                          CommonRoleGroups.CONTENT_EDITORS
                                       }
                                    >
                                       Validate
                                    </PermissionButton>
                                    <PermissionButton
                                       icon={<SyncOutlined />}
                                       onClick={() => {
                                          void handleSync(connection);
                                       }}
                                       loading={isBusy}
                                       allowedProjectRoles={
                                          CommonRoleGroups.CONTENT_EDITORS
                                       }
                                    >
                                       Sync Now
                                    </PermissionButton>
                                    {!isManaged && (
                                       <PermissionButton
                                          icon={<EditOutlined />}
                                          onClick={() =>
                                             openEditModal(connection)
                                          }
                                          allowedProjectRoles={
                                             CommonRoleGroups.CONTENT_EDITORS
                                          }
                                       >
                                          Edit
                                       </PermissionButton>
                                    )}
                                    {!isManaged && (
                                       <PermissionButton
                                          danger
                                          icon={<DeleteOutlined />}
                                          onClick={() =>
                                             handleDelete(connection)
                                          }
                                          allowedProjectRoles={
                                             CommonRoleGroups.CONTENT_EDITORS
                                          }
                                       >
                                          Delete
                                       </PermissionButton>
                                    )}
                                 </Flex>
                              </Space>
                           </Card>
                        </Col>
                     );
                  })}
               </Row>
            )}
         </Space>

         <Modal
            title={editingConnection ? "Edit Data Source" : "New Data Source"}
            open={isModalOpen}
            onCancel={closeModal}
            width={720}
            footer={
               <Flex justify="space-between" gap="small">
                  <Button onClick={closeModal}>Cancel</Button>
                  <Space>
                     {modalStep > 0 && (
                        <Button
                           onClick={() => {
                              setModalStep((current) =>
                                 Math.max(current - 1, 0)
                              );
                           }}
                        >
                           Back
                        </Button>
                     )}
                     {isLastModalStep ? (
                        <Button
                           type="primary"
                           loading={submitting}
                           onClick={() => {
                              void handleSubmit();
                           }}
                        >
                           {editingConnection
                              ? "Save Changes"
                              : "Create Data Source"}
                        </Button>
                     ) : (
                        <Button
                           type="primary"
                           onClick={() => {
                              void handleNextStep();
                           }}
                        >
                           Next
                        </Button>
                     )}
                  </Space>
               </Flex>
            }
            destroyOnHidden
         >
            <Form
               form={form}
               layout="vertical"
               initialValues={{ enabled: true }}
            >
               <Space
                  orientation="vertical"
                  size="large"
                  style={{ width: "100%" }}
               >
                  <Steps
                     current={modalStep}
                     size="small"
                     items={modalSteps.map((step) => ({
                        title: step.title,
                        content: step.description
                     }))}
                  />

                  {modalStep === 0 && (
                     <Space
                        orientation="vertical"
                        size="middle"
                        style={{ width: "100%" }}
                     >
                        <Typography.Paragraph type="secondary">
                           Pick the kind of database you want this project to
                           connect to.
                        </Typography.Paragraph>

                        <Form.Item
                           label="Provider"
                           name="providerKind"
                           rules={[
                              { required: true, message: "Select a provider" }
                           ]}
                        >
                           <Select
                              disabled={Boolean(editingConnection)}
                              options={createableProviders.map((provider) => ({
                                 label: provider.displayName,
                                 value: provider.providerKind
                              }))}
                              onChange={handleProviderChange}
                           />
                        </Form.Item>
                     </Space>
                  )}

                  {modalStep === 1 && (
                     <Space
                        orientation="vertical"
                        size="small"
                        style={{ width: "100%" }}
                     >
                        <Row gutter={[12, 0]}>
                           <Col span={18}>
                              <Form.Item
                                 label="Display Name"
                                 name="displayName"
                                 style={{ marginBottom: 12 }}
                                 rules={[
                                    {
                                       required: true,
                                       message: "Enter a data source name"
                                    }
                                 ]}
                              >
                                 <Input disabled={isEditingManagedConnection} />
                              </Form.Item>
                           </Col>
                           <Col span={6}>
                              <Form.Item
                                 label="Enabled"
                                 name="enabled"
                                 valuePropName="checked"
                                 style={{ marginBottom: 12 }}
                              >
                                 <Switch
                                    disabled={isEditingManagedConnection}
                                 />
                              </Form.Item>
                           </Col>
                           <Col span={24}>
                              <Form.Item
                                 label="Description"
                                 name="description"
                                 style={{ marginBottom: 12 }}
                              >
                                 <Input.TextArea
                                    rows={2}
                                    disabled={isEditingManagedConnection}
                                 />
                              </Form.Item>
                           </Col>
                        </Row>

                        <ConnectionSettingsFields
                           fields={formFields}
                           disabled={isEditingManagedConnection}
                        />
                     </Space>
                  )}

                  {modalStep === 2 && hasCredentialStep && formProvider && (
                     <Space
                        orientation="vertical"
                        size="small"
                        style={{ width: "100%" }}
                     >
                        <Row gutter={[12, 0]}>
                           <Col span={12}>
                              <Form.Item
                                 label="Authentication"
                                 name="authType"
                                 style={{ marginBottom: 12 }}
                              >
                                 <Select
                                    disabled={isEditingManagedConnection}
                                    options={formProvider.authTypes.map(
                                       (value) => ({
                                          label: getAuthTypeLabel(value),
                                          value
                                       })
                                    )}
                                 />
                              </Form.Item>
                           </Col>

                           <Col span={12}>
                              <Form.Item
                                 label="Execution Mode"
                                 name="executionMode"
                                 style={{ marginBottom: 12 }}
                              >
                                 <Select
                                    disabled={isEditingManagedConnection}
                                    options={formProvider.executionModes.map(
                                       (value) => ({
                                          label:
                                             getExecutionModeLabel(value) ||
                                             value,
                                          value
                                       })
                                    )}
                                 />
                              </Form.Item>
                           </Col>
                        </Row>

                        {editingConnection && (
                           <Alert
                              type={hasConfiguredSecret ? "info" : "warning"}
                              showIcon
                              title={
                                 hasPendingSecretValue
                                    ? "A new secret will be stored when you save this data source."
                                    : hasConfiguredSecret
                                      ? "A secret is already stored for this data source."
                                      : "No secret is currently stored for this data source."
                              }
                              description={
                                 hasPendingSecretValue
                                    ? "Save your changes to replace the current password or token with the new value entered here."
                                    : hasConfiguredSecret
                                      ? "Leave Secret Value blank to keep the existing password or token. Enter a new value only when you want to replace it."
                                      : "Provide a Secret Value before validating if this data source requires a password."
                              }
                           />
                        )}

                        <Row gutter={[12, 0]}>
                           <Col span={12}>
                              <Form.Item
                                 label="Secret Value"
                                 name="secretValue"
                                 style={{ marginBottom: 12 }}
                                 extra={
                                    hasConfiguredSecret &&
                                    !hasPendingSecretValue
                                       ? "Optional. Leave blank to keep the existing stored password or token."
                                       : "Optional. Provide a password or token to store with this data source."
                                 }
                              >
                                 <Input.Password
                                    disabled={isEditingManagedConnection}
                                 />
                              </Form.Item>
                           </Col>

                           <Col span={12}>
                              <Form.Item
                                 label="Secret Reference"
                                 name="secretRef"
                                 style={{ marginBottom: 12 }}
                                 extra="Optional. Use this if your deployment resolves secrets by reference."
                              >
                                 <Input disabled={isEditingManagedConnection} />
                              </Form.Item>
                           </Col>
                        </Row>
                     </Space>
                  )}

                  {modalStep === modalSteps.length - 1 && (
                     <DataSourceReviewPanel
                        values={watchedValues}
                        provider={formProvider}
                        editingConnection={editingConnection}
                     />
                  )}
               </Space>
            </Form>
         </Modal>
      </PageContainer>
   );
};

export default ProjectCatalogsPage;
