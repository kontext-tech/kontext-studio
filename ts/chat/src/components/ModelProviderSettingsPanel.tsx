import type { ApiErrorResult } from "@kontext-labs/common";
import {
   DeleteOutlined,
   PlusOutlined,
   RightOutlined
} from "@kontext-labs/icons";
import { useService } from "@kontext-labs/app-runtime/hooks";
import type {
   FoundationModel,
   ModelConnection,
   ModelConnectionCredentialRefs,
   ModelConnectionKind,
   ModelConnectionProviderConfig,
   ModelProviderDefinition
} from "@kontext-labs/schema";
import type { UiFeedback } from "@kontext-labs/ui";
import {
   Alert,
   AutoComplete,
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
   Switch,
   Tabs,
   Tag,
   Typography,
   theme
} from "antd";
import {
   forwardRef,
   useCallback,
   useEffect,
   useImperativeHandle,
   useMemo,
   useState
} from "react";
import { ModelProviderService } from "../ModelProviderService";
import {
   filterFoundationModelsForProvider,
   getConfiguredCredentialLabels,
   getCredentialFieldMeta,
   getDefaultEndpointBaseUrl,
   getEffectiveConfigFields,
   getEffectiveCredentialFields,
   getProviderDefinition,
   getProviderFormCopy,
   getProviderLabel,
   getValidationMeta,
   getVisibleCredentialFields,
   pruneCredentialRefs,
   pruneProviderConfig,
   type CredentialFieldName
} from "./modelProviderFormConfig";

const { Paragraph, Text, Title } = Typography;

export interface ModelProviderSettingsPanelProps {
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   loadFoundationModels: () => Promise<FoundationModel[]>;
   ui?: UiFeedback;
   showDescription?: boolean;
   displayMode?: "card" | "plain";
}

export interface ModelProviderSettingsPanelHandle {
   openAddConnection: () => void;
}

type SupportedModelOption = {
   label: string;
   value: string;
   description?: string | null;
};

type ReasoningEffortValue = "low" | "medium" | "high";

type ConnectionFormValues = {
   connectionKind: ModelConnectionKind;
   canonicalModelId?: string;
   displayName?: string;
   providerConfig?: ModelConnectionProviderConfig;
   credentialInputs?: Partial<ModelConnectionCredentialRefs>;
   reasoningEffort?: ReasoningEffortValue;
   enabled?: boolean;
   isDefault?: boolean;
};

const getRequestErrorMessage = (
   fallbackMessage: string,
   error?: { title?: string; messages?: string[] }
) => error?.messages?.[0] || error?.title || fallbackMessage;

const getUnknownErrorMessage = (error: unknown, fallbackMessage: string) =>
   error instanceof Error && error.message ? error.message : fallbackMessage;

export const ModelProviderSettingsPanel = forwardRef<
   ModelProviderSettingsPanelHandle,
   ModelProviderSettingsPanelProps
>(function ModelProviderSettingsPanel(
   {
      errorHandler,
      loadFoundationModels,
      ui,
      showDescription = true,
      displayMode = "card"
   },
   ref
) {
   const modelProviderService = useService(ModelProviderService, errorHandler);
   const [connections, setConnections] = useState<ModelConnection[]>([]);
   const [providerDefinitions, setProviderDefinitions] = useState<
      ModelProviderDefinition[]
   >([]);
   const [form] = Form.useForm<ConnectionFormValues>();
   const [editingConnection, setEditingConnection] =
      useState<ModelConnection | null>(null);
   const [isEditorOpen, setIsEditorOpen] = useState(false);
   const [activeConnectionKind, setActiveConnectionKind] = useState<string>("");
   const { token } = theme.useToken();
   const [foundationModels, setFoundationModels] = useState<FoundationModel[]>(
      []
   );
   const [foundationModelLoadError, setFoundationModelLoadError] = useState<
      string | null
   >(null);
   const watchedConnectionKind = Form.useWatch("connectionKind", form);
   const watchedCanonicalModelId = Form.useWatch("canonicalModelId", form);
   const selectedProviderDefinition = useMemo(
      () =>
         getProviderDefinition(
            providerDefinitions,
            watchedConnectionKind ?? null
         ),
      [providerDefinitions, watchedConnectionKind]
   );
   const effectiveConfigFields = useMemo(
      () => getEffectiveConfigFields(selectedProviderDefinition),
      [selectedProviderDefinition]
   );
   const visibleCredentialFields = useMemo(
      () => getVisibleCredentialFields(selectedProviderDefinition),
      [selectedProviderDefinition]
   );
   const effectiveCredentialFields = useMemo(
      () => getEffectiveCredentialFields(selectedProviderDefinition),
      [selectedProviderDefinition]
   );
   const isEditingActiveConnectionKind =
      editingConnection !== null &&
      editingConnection.connectionKind === watchedConnectionKind;
   const existingCredentialRefs = isEditingActiveConnectionKind
      ? editingConnection.credentialRefs
      : undefined;
   const existingApiKeyRef = isEditingActiveConnectionKind
      ? editingConnection.secretRef ||
        editingConnection.credentialRefs?.apiKeyRef
      : undefined;

   useEffect(() => {
      let isCancelled = false;

      const loadInitialData = async () => {
         const [connectionsResult, providersResult, foundationModelsResult] =
            await Promise.allSettled([
               modelProviderService.getModelProviders(),
               modelProviderService.getModelProviderDefinitions(),
               loadFoundationModels()
            ]);

         if (isCancelled) {
            return;
         }

         if (connectionsResult.status === "fulfilled") {
            if (
               connectionsResult.value.succeed &&
               connectionsResult.value.data
            ) {
               setConnections(connectionsResult.value.data);
            }
         } else {
            console.error(
               "Failed to load model providers",
               connectionsResult.reason
            );
         }

         if (providersResult.status === "fulfilled") {
            if (providersResult.value.succeed && providersResult.value.data) {
               const nextProviderDefinitions = providersResult.value.data;
               setProviderDefinitions(nextProviderDefinitions);
               setActiveConnectionKind(
                  (current) =>
                     current || nextProviderDefinitions[0]?.connectionKind || ""
               );
            }
         } else {
            console.error(
               "Failed to load model provider definitions",
               providersResult.reason
            );
         }

         if (foundationModelsResult.status === "fulfilled") {
            setFoundationModels(foundationModelsResult.value);
            setFoundationModelLoadError(null);
            return;
         }

         const errorMessage = getUnknownErrorMessage(
            foundationModelsResult.reason,
            "Failed to load the curated foundation model catalog."
         );
         setFoundationModels([]);
         setFoundationModelLoadError(errorMessage);
         ui?.error(errorMessage);
         console.error(
            "Failed to load curated foundation models",
            foundationModelsResult.reason
         );
      };

      void loadInitialData();

      return () => {
         isCancelled = true;
      };
   }, [loadFoundationModels, modelProviderService, ui]);

   useEffect(() => {
      if (
         providerDefinitions.length > 0 &&
         !providerDefinitions.some(
            (definition) => definition.connectionKind === activeConnectionKind
         )
      ) {
         setActiveConnectionKind(providerDefinitions[0]?.connectionKind || "");
      }
   }, [activeConnectionKind, providerDefinitions]);

   const filteredModels = useMemo(
      () =>
         filterFoundationModelsForProvider(
            foundationModels,
            watchedConnectionKind
         ),
      [foundationModels, watchedConnectionKind]
   );
   const modelOptions = useMemo<SupportedModelOption[]>(
      () =>
         filteredModels.map((model) => ({
            label: model.name,
            value: model.canonicalModelId,
            description: model.description
         })),
      [filteredModels]
   );
   const selectedFoundationModel = useMemo(
      () =>
         foundationModels.find(
            (model) => model.canonicalModelId === watchedCanonicalModelId
         ),
      [foundationModels, watchedCanonicalModelId]
   );
   const showReasoningEffort = Boolean(
      selectedFoundationModel?.reasoningSupported
   );
   const connectionKindTabItems = useMemo(
      () =>
         providerDefinitions.map((providerDefinition) => ({
            key: providerDefinition.connectionKind,
            label: `${providerDefinition.displayName} (${connections.filter((connection) => connection.connectionKind === providerDefinition.connectionKind).length})`
         })),
      [connections, providerDefinitions]
   );
   const visibleConnections = useMemo(
      () =>
         activeConnectionKind
            ? connections.filter(
                 (connection) =>
                    connection.connectionKind === activeConnectionKind
              )
            : connections,
      [activeConnectionKind, connections]
   );

   const resetEditorState = useCallback(() => {
      setEditingConnection(null);
      form.resetFields();
      setIsEditorOpen(false);
   }, [form]);

   const openEditor = useCallback(
      (connectionKind: string, connection?: ModelConnection | null) => {
         const providerDefinition = getProviderDefinition(
            providerDefinitions,
            connectionKind
         );
         const endpointBaseUrl =
            connection?.providerConfig?.endpointBaseUrl ||
            connection?.endpointBaseUrl ||
            getDefaultEndpointBaseUrl(providerDefinition);

         form.resetFields();
         form.setFieldsValue({
            connectionKind: connectionKind as ModelConnectionKind,
            canonicalModelId: connection?.canonicalModelId,
            displayName: connection?.displayName,
            providerConfig: {
               endpointBaseUrl,
               region: connection?.providerConfig?.region,
               projectId: connection?.providerConfig?.projectId,
               location: connection?.providerConfig?.location,
               apiVersion: connection?.providerConfig?.apiVersion
            },
            credentialInputs: {},
            reasoningEffort: connection?.reasoningEffort ?? undefined,
            enabled: connection?.enabled ?? true,
            isDefault: connection?.isDefault ?? false
         });
         setEditingConnection(connection ?? null);
         setIsEditorOpen(true);
      },
      [form, providerDefinitions]
   );

   const handleOpenAddModal = useCallback(() => {
      const defaultConnectionKind =
         activeConnectionKind ||
         providerDefinitions[0]?.connectionKind ||
         "lm_studio";
      openEditor(defaultConnectionKind, null);
   }, [activeConnectionKind, openEditor, providerDefinitions]);

   const handleQuickConnect = useCallback(
      (connectionKind: string) => {
         const providerDefinition = getProviderDefinition(
            providerDefinitions,
            connectionKind
         );
         const defaultModelId = providerDefinition?.defaultModelId || undefined;
         const curatedModel = defaultModelId
            ? foundationModels.find(
                 (model) => model.canonicalModelId === defaultModelId
              )
            : undefined;

         openEditor(connectionKind, null);
         form.setFieldsValue({
            canonicalModelId: defaultModelId,
            displayName:
               curatedModel?.name ||
               providerDefinition?.displayName ||
               connectionKind
         });
      },
      [form, foundationModels, openEditor, providerDefinitions]
   );

   useImperativeHandle(
      ref,
      () => ({
         openAddConnection: handleOpenAddModal
      }),
      [handleOpenAddModal]
   );

   const handleEdit = (connection: ModelConnection) => {
      openEditor(connection.connectionKind, connection);
   };

   const handleDelete = async (id: string) => {
      const result = await modelProviderService.deleteModelProvider(id);
      if (result.succeed) {
         setConnections((previousConnections) =>
            previousConnections.filter((connection) => connection.id !== id)
         );
         if (editingConnection?.id === id) {
            resetEditorState();
         }
         ui?.success("Provider removed");
         return;
      }

      ui?.error(
         getRequestErrorMessage("Failed to remove provider", result.error)
      );
   };

   const handleConnectionKindChange = (connectionKind: string) => {
      const providerDefinition = getProviderDefinition(
         providerDefinitions,
         connectionKind
      );

      form.setFieldsValue({
         canonicalModelId: undefined,
         displayName: undefined,
         providerConfig: {
            endpointBaseUrl: getDefaultEndpointBaseUrl(providerDefinition),
            region: undefined,
            projectId: undefined,
            location: undefined,
            apiVersion: undefined
         },
         credentialInputs: {}
      });
   };

   const handleFoundationModelChange = (foundationModelId: string) => {
      const foundationModel = foundationModels.find(
         (model) => model.canonicalModelId === foundationModelId
      );

      if (foundationModel) {
         form.setFieldValue("displayName", foundationModel.name);
      }
   };

   const handleCancelEdit = () => {
      resetEditorState();
   };

   const handleSubmit = async () => {
      try {
         const values = await form.validateFields();

         const canonicalModelId = values.canonicalModelId?.trim();
         if (!canonicalModelId || !values.connectionKind) {
            ui?.error("Please enter a model id");
            return;
         }

         const providerDefinition = getProviderDefinition(
            providerDefinitions,
            values.connectionKind
         );
         if (!providerDefinition) {
            ui?.error("The selected provider is not available");
            return;
         }

         // The runtime provider model name is derived server-side from curated
         // metadata (or the canonical id for custom models), so the form only
         // needs to send the canonical model id.
         const curatedModel = foundationModels.find(
            (model) => model.canonicalModelId === canonicalModelId
         );

         const providerConfig = pruneProviderConfig(
            { ...values.providerConfig },
            providerDefinition
         );
         const credentialRefs = pruneCredentialRefs(
            {
               apiKeyRef:
                  values.credentialInputs?.apiKeyRef ||
                  existingApiKeyRef ||
                  undefined,
               accessKeyIdRef:
                  values.credentialInputs?.accessKeyIdRef ||
                  existingCredentialRefs?.accessKeyIdRef ||
                  undefined,
               secretAccessKeyRef:
                  values.credentialInputs?.secretAccessKeyRef ||
                  existingCredentialRefs?.secretAccessKeyRef ||
                  undefined,
               sessionTokenRef:
                  values.credentialInputs?.sessionTokenRef ||
                  existingCredentialRefs?.sessionTokenRef ||
                  undefined
            },
            providerDefinition
         );
         const hasConfiguredCredentials = Boolean(
            credentialRefs && Object.values(credentialRefs).some(Boolean)
         );

         const connectionData: ModelConnection = {
            id: editingConnection?.id,
            sourceType: editingConnection?.sourceType ?? "user_managed",
            adapterType: providerDefinition.adapterType,
            connectionKind: values.connectionKind,
            canonicalModelId,
            displayName:
               values.displayName || curatedModel?.name || canonicalModelId,
            providerConfig,
            credentialRefs,
            endpointBaseUrl: providerConfig?.endpointBaseUrl,
            secretRef: credentialRefs?.apiKeyRef,
            secretConfigured: hasConfiguredCredentials,
            reasoningEffort: values.reasoningEffort,
            isDefault: Boolean(values.isDefault),
            enabled: values.enabled !== false,
            validationState: editingConnection?.validationState ?? "unknown",
            ownerId: editingConnection?.ownerId
         };

         if (editingConnection?.id) {
            const result = await modelProviderService.updateModelProvider(
               editingConnection.id,
               connectionData
            );

            if (result.succeed && result.data) {
               const updatedConnection = result.data;
               setConnections((previousConnections): ModelConnection[] =>
                  previousConnections.map((connection) =>
                     connection.id === editingConnection.id
                        ? updatedConnection
                        : connection
                  )
               );
               ui?.success("Provider updated");
               resetEditorState();
               return;
            }

            ui?.error(
               getRequestErrorMessage("Failed to update provider", result.error)
            );
            return;
         }

         const result =
            await modelProviderService.createModelProvider(connectionData);

         if (result.succeed && result.data) {
            const createdConnection = result.data;
            setConnections((previousConnections): ModelConnection[] => [
               ...previousConnections,
               createdConnection
            ]);
            ui?.success("Provider added");
            resetEditorState();
            return;
         }

         ui?.error(
            getRequestErrorMessage("Failed to add provider", result.error)
         );
      } catch (error) {
         console.error("Validation failed", error);
      }
   };

   const editorTitle = editingConnection ? "Edit Provider" : "Add Provider";
   const showContainerCard = displayMode === "card";
   const showInlineAddAction = displayMode === "card";
   const providerCopy = getProviderFormCopy(watchedConnectionKind);
   const showEndpointField =
      effectiveConfigFields.required.has("endpointBaseUrl") ||
      effectiveConfigFields.optional.has("endpointBaseUrl") ||
      Boolean(selectedProviderDefinition?.supportsCustomEndpoint) ||
      Boolean(selectedProviderDefinition?.defaultEndpointBaseUrl);
   const showRegionField =
      effectiveConfigFields.required.has("region") ||
      effectiveConfigFields.optional.has("region");
   const showProjectIdField =
      effectiveConfigFields.required.has("projectId") ||
      effectiveConfigFields.optional.has("projectId");
   const showLocationField =
      effectiveConfigFields.required.has("location") ||
      effectiveConfigFields.optional.has("location");
   const showApiVersionField =
      effectiveConfigFields.required.has("apiVersion") ||
      effectiveConfigFields.optional.has("apiVersion");
   const showAdvancedSettings =
      showEndpointField ||
      showRegionField ||
      showProjectIdField ||
      showLocationField ||
      showApiVersionField;

   const quickConnectDefinitions = useMemo(
      () =>
         ["ollama", "lm_studio"]
            .map(
               (connectionKind) =>
                  getProviderDefinition(providerDefinitions, connectionKind) ??
                  null
            )
            .filter(
               (definition): definition is ModelProviderDefinition =>
                  definition !== null
            ),
      [providerDefinitions]
   );

   const connectionListContent =
      connections.length === 0 ? (
         <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
               <Space
                  direction="vertical"
                  size={4}
                  style={{ textAlign: "center" }}
               >
                  <Text strong>No providers configured</Text>
                  <Text type="secondary">
                     {showInlineAddAction
                        ? "Connect a local runtime in one click, or add any provider manually."
                        : "Use Add Provider above to make curated models available across chats and AI tools."}
                  </Text>
               </Space>
            }
         >
            {quickConnectDefinitions.length > 0 && (
               <Space
                  direction="vertical"
                  size={token.sizeSM}
                  style={{ width: "100%", maxWidth: 480 }}
               >
                  {quickConnectDefinitions.map((definition) => {
                     const modelId = definition.defaultModelId || undefined;
                     const modelName = modelId
                        ? foundationModels.find(
                             (model) => model.canonicalModelId === modelId
                          )?.name
                        : undefined;
                     return (
                        <Card
                           key={definition.connectionKind}
                           size="small"
                           hoverable
                           onClick={() =>
                              handleQuickConnect(definition.connectionKind)
                           }
                           style={{ textAlign: "left" }}
                        >
                           <Flex align="center" justify="space-between" gap={8}>
                              <Space
                                 direction="vertical"
                                 size={0}
                                 style={{ minWidth: 0 }}
                              >
                                 <Text strong>
                                    Connect {definition.displayName}
                                 </Text>
                                 <Text
                                    type="secondary"
                                    style={{ fontSize: 12 }}
                                 >
                                    {modelName ?? "Default local model"} at{" "}
                                    {getDefaultEndpointBaseUrl(definition)}
                                 </Text>
                              </Space>
                              <RightOutlined
                                 style={{ color: token.colorTextTertiary }}
                              />
                           </Flex>
                        </Card>
                     );
                  })}
               </Space>
            )}

            {showInlineAddAction && (
               <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={handleOpenAddModal}
                  style={{ marginTop: token.marginSM }}
               >
                  Add Provider
               </Button>
            )}
         </Empty>
      ) : visibleConnections.length === 0 ? (
         <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
               <Space
                  direction="vertical"
                  size={4}
                  style={{ textAlign: "center" }}
               >
                  <Text strong>No providers for this type</Text>
                  <Text type="secondary">
                     Switch provider types or add a new provider.
                  </Text>
               </Space>
            }
         />
      ) : (
         <Space
            direction="vertical"
            size={token.sizeSM}
            style={{ width: "100%" }}
         >
            {visibleConnections.map((connection) => {
               const validationMeta = getValidationMeta(
                  connection.validationState
               );
               const configuredCredentialLabels =
                  getConfiguredCredentialLabels(connection);

               return (
                  <Card
                     key={connection.id ?? connection.canonicalModelId}
                     size="small"
                     style={{ backgroundColor: token.colorFillAlter }}
                     styles={{ body: { padding: token.padding } }}
                  >
                     <Flex
                        align="start"
                        justify="space-between"
                        gap={token.sizeSM}
                        wrap
                     >
                        <Space
                           direction="vertical"
                           size={token.sizeXXS}
                           style={{ flex: 1, minWidth: 280 }}
                        >
                           <Space wrap size={[token.sizeXXS, token.sizeXXS]}>
                              <Title level={5} style={{ margin: 0 }}>
                                 {connection.displayName}
                              </Title>
                              {connection.isDefault && (
                                 <Tag color="blue">Default</Tag>
                              )}
                              <Tag
                                 color={
                                    connection.enabled ? "success" : "default"
                                 }
                              >
                                 {connection.enabled ? "Enabled" : "Disabled"}
                              </Tag>
                              <Tag color={validationMeta.color}>
                                 {validationMeta.label}
                              </Tag>
                           </Space>

                           <Text type="secondary">
                              {getProviderLabel(
                                 connection.connectionKind,
                                 providerDefinitions
                              )}{" "}
                              provider using {connection.canonicalModelId}
                           </Text>

                           <Space wrap size={[token.sizeSM, token.sizeXXS]}>
                              <Text type="secondary">
                                 Runtime model:{" "}
                                 {connection.providerConfig
                                    ?.providerModelName ||
                                    connection.providerModelName ||
                                    connection.canonicalModelId}
                              </Text>
                              <Text type="secondary">
                                 Credentials:{" "}
                                 {configuredCredentialLabels.length > 0
                                    ? configuredCredentialLabels.join(", ")
                                    : "not set"}
                              </Text>
                              {connection.providerConfig?.region && (
                                 <Text type="secondary">
                                    Region: {connection.providerConfig.region}
                                 </Text>
                              )}
                           </Space>

                           {connection.providerConfig?.endpointBaseUrl && (
                              <Text code>
                                 {connection.providerConfig.endpointBaseUrl}
                              </Text>
                           )}
                        </Space>

                        <Space size={token.sizeXXS}>
                           <Button
                              type="link"
                              size="small"
                              onClick={() => handleEdit(connection)}
                           >
                              Edit
                           </Button>
                           <Button
                              type="text"
                              danger
                              size="small"
                              icon={<DeleteOutlined />}
                              onClick={() =>
                                 connection.id && handleDelete(connection.id)
                              }
                           />
                        </Space>
                     </Flex>
                  </Card>
               );
            })}
         </Space>
      );

   return (
      <>
         {foundationModelLoadError && (
            <Alert
               type="error"
               showIcon
               message="Foundation model catalog unavailable"
               description={foundationModelLoadError}
               style={{ marginBottom: token.marginMD }}
            />
         )}

         {connectionKindTabItems.length > 1 && (
            <Tabs
               type="line"
               activeKey={activeConnectionKind}
               onChange={setActiveConnectionKind}
               items={connectionKindTabItems}
               style={{ marginBottom: token.marginMD }}
            />
         )}

         {showDescription && (
            <Paragraph type="secondary">
               Configure the model endpoints available to your AI features.
            </Paragraph>
         )}

         {showContainerCard ? (
            <Card
               title={<Text strong>Configured Providers</Text>}
               extra={
                  <Button
                     type="primary"
                     icon={<PlusOutlined />}
                     onClick={handleOpenAddModal}
                  >
                     Add Provider
                  </Button>
               }
               styles={{
                  body: { padding: token.paddingLG }
               }}
            >
               {connectionListContent}
            </Card>
         ) : (
            connectionListContent
         )}

         <Modal
            title={editorTitle}
            open={isEditorOpen}
            onCancel={handleCancelEdit}
            onOk={handleSubmit}
            okText={editingConnection ? "Update Provider" : "Add Provider"}
            width={1000}
            style={{ top: token.marginLG }}
            styles={{
               body: {
                  maxHeight: "72vh",
                  overflowY: "auto",
                  overflowX: "hidden"
               }
            }}
            destroyOnHidden
         >
            <Form form={form} layout="vertical">
               <Paragraph
                  type="secondary"
                  style={{ marginBottom: token.marginMD }}
               >
                  {providerCopy.basicsDescription}
               </Paragraph>

               <Row gutter={token.marginLG}>
                  <Col xs={24} lg={14}>
                     <Space
                        direction="vertical"
                        size="middle"
                        style={{ width: "100%" }}
                     >
                        <Form.Item
                           name="connectionKind"
                           label="Provider"
                           rules={[{ required: true }]}
                        >
                           <Select
                              onChange={handleConnectionKindChange}
                              options={providerDefinitions.map(
                                 (providerDefinition) => ({
                                    label: providerDefinition.displayName,
                                    value: providerDefinition.connectionKind
                                 })
                              )}
                           />
                        </Form.Item>

                        <Form.Item
                           name="canonicalModelId"
                           label="Model"
                           rules={[
                              {
                                 required: true,
                                 message: "Please enter or select a model"
                              }
                           ]}
                           extra={
                              foundationModelLoadError
                                 ? foundationModelLoadError
                                 : "Pick a curated model or type any model id your provider supports."
                           }
                        >
                           <AutoComplete
                              placeholder="e.g. openai/gpt-4o-mini"
                              options={modelOptions}
                              onChange={handleFoundationModelChange}
                              filterOption={(inputValue, option) =>
                                 (option?.label ?? "")
                                    .toString()
                                    .toLowerCase()
                                    .includes(inputValue.toLowerCase()) ||
                                 (option?.value ?? "")
                                    .toString()
                                    .toLowerCase()
                                    .includes(inputValue.toLowerCase())
                              }
                           />
                        </Form.Item>

                        <Form.Item
                           name="displayName"
                           label="Display Name"
                           rules={[
                              {
                                 required: true,
                                 message: "Please enter a display name"
                              }
                           ]}
                        >
                           <Input
                              placeholder={providerCopy.displayNamePlaceholder}
                           />
                        </Form.Item>

                        {showReasoningEffort && (
                           <Form.Item
                              name="reasoningEffort"
                              label="Thinking level"
                              extra="Optional. Applies only to models that support reasoning."
                           >
                              <Select
                                 allowClear
                                 placeholder="Provider default"
                                 options={[
                                    { label: "Low", value: "low" },
                                    { label: "Medium", value: "medium" },
                                    { label: "High", value: "high" }
                                 ]}
                              />
                           </Form.Item>
                        )}

                        {showAdvancedSettings && (
                           <>
                              <Text strong>Provider settings</Text>
                              <Row gutter={token.marginMD}>
                                 {showEndpointField && (
                                    <Col span={12}>
                                       <Form.Item
                                          name={[
                                             "providerConfig",
                                             "endpointBaseUrl"
                                          ]}
                                          label="Base URL"
                                          rules={[
                                             {
                                                required:
                                                   effectiveConfigFields.required.has(
                                                      "endpointBaseUrl"
                                                   ),
                                                message: "Base URL is required"
                                             },
                                             {
                                                type: "url",
                                                message: "Invalid URL"
                                             }
                                          ]}
                                       >
                                          <Input
                                             placeholder={
                                                providerCopy.endpointPlaceholder ||
                                                getDefaultEndpointBaseUrl(
                                                   selectedProviderDefinition
                                                ) ||
                                                "https://api.example.com/v1"
                                             }
                                          />
                                       </Form.Item>
                                    </Col>
                                 )}

                                 {showRegionField && (
                                    <Col span={12}>
                                       <Form.Item
                                          name={["providerConfig", "region"]}
                                          label="AWS Region"
                                          rules={[
                                             {
                                                required:
                                                   effectiveConfigFields.required.has(
                                                      "region"
                                                   ),
                                                message:
                                                   "AWS region is required"
                                             }
                                          ]}
                                       >
                                          <Input placeholder="ap-southeast-2" />
                                       </Form.Item>
                                    </Col>
                                 )}

                                 {showProjectIdField && (
                                    <Col span={12}>
                                       <Form.Item
                                          name={["providerConfig", "projectId"]}
                                          label="Google Cloud Project ID"
                                          rules={[
                                             {
                                                required:
                                                   effectiveConfigFields.required.has(
                                                      "projectId"
                                                   ),
                                                message:
                                                   "Project ID is required"
                                             }
                                          ]}
                                       >
                                          <Input placeholder="my-gcp-project" />
                                       </Form.Item>
                                    </Col>
                                 )}

                                 {showLocationField && (
                                    <Col span={12}>
                                       <Form.Item
                                          name={["providerConfig", "location"]}
                                          label="Google Cloud Location"
                                          rules={[
                                             {
                                                required:
                                                   effectiveConfigFields.required.has(
                                                      "location"
                                                   ),
                                                message: "Location is required"
                                             }
                                          ]}
                                       >
                                          <Input placeholder="us-central1" />
                                       </Form.Item>
                                    </Col>
                                 )}

                                 {showApiVersionField && (
                                    <Col span={12}>
                                       <Form.Item
                                          name={[
                                             "providerConfig",
                                             "apiVersion"
                                          ]}
                                          label="Azure API Version"
                                          rules={[
                                             {
                                                required:
                                                   effectiveConfigFields.required.has(
                                                      "apiVersion"
                                                   ),
                                                message:
                                                   "API version is required"
                                             }
                                          ]}
                                       >
                                          <Input placeholder="2024-10-21" />
                                       </Form.Item>
                                    </Col>
                                 )}
                              </Row>
                           </>
                        )}
                     </Space>
                  </Col>

                  <Col xs={24} lg={10}>
                     <Space
                        direction="vertical"
                        size="large"
                        style={{ width: "100%" }}
                     >
                        <Space
                           direction="vertical"
                           size="middle"
                           style={{ width: "100%" }}
                        >
                           <Text strong>Availability</Text>
                           <Paragraph
                              type="secondary"
                              style={{ marginBottom: 0 }}
                           >
                              Choose whether this provider is enabled and
                              whether it should be the default for your AI
                              tools.
                           </Paragraph>

                           <Form.Item
                              name="enabled"
                              label="Enabled"
                              valuePropName="checked"
                              style={{ marginBottom: token.marginSM }}
                           >
                              <Switch />
                           </Form.Item>

                           <Form.Item
                              name="isDefault"
                              label="Default Provider"
                              valuePropName="checked"
                              style={{ marginBottom: 0 }}
                           >
                              <Switch />
                           </Form.Item>
                        </Space>

                        <Space
                           direction="vertical"
                           size="middle"
                           style={{ width: "100%" }}
                        >
                           <Text strong>Authentication</Text>
                           <Paragraph
                              type="secondary"
                              style={{ marginBottom: 0 }}
                           >
                              {providerCopy.authDescription}
                           </Paragraph>

                           {editingConnection && (
                              <Space wrap size={[token.sizeXXS, token.sizeXXS]}>
                                 <Text type="secondary">
                                    Existing credentials:
                                 </Text>
                                 {getConfiguredCredentialLabels(
                                    editingConnection
                                 ).length > 0 ? (
                                    getConfiguredCredentialLabels(
                                       editingConnection
                                    ).map((label) => (
                                       <Tag key={label} color="success">
                                          {label}
                                       </Tag>
                                    ))
                                 ) : (
                                    <Tag color="default">Not set</Tag>
                                 )}
                              </Space>
                           )}

                           {visibleCredentialFields.length === 0 ? (
                              <Text type="secondary">
                                 This provider does not require stored
                                 credentials in this rollout.
                              </Text>
                           ) : (
                              visibleCredentialFields.map((fieldName) => {
                                 const fieldMeta =
                                    getCredentialFieldMeta(fieldName);
                                 const existingValue =
                                    fieldName === "apiKeyRef"
                                       ? existingApiKeyRef
                                       : existingCredentialRefs?.[
                                            fieldName as CredentialFieldName
                                         ];

                                 return (
                                    <Form.Item
                                       key={fieldName}
                                       name={["credentialInputs", fieldName]}
                                       label={fieldMeta.label}
                                       rules={[
                                          {
                                             required:
                                                effectiveCredentialFields.required.has(
                                                   fieldName
                                                ) && !existingValue,
                                             message: `${fieldMeta.label} is required`
                                          }
                                       ]}
                                       extra={
                                          editingConnection
                                             ? fieldMeta.editHelp
                                             : fieldMeta.createHelp
                                       }
                                    >
                                       <Input.Password
                                          placeholder={fieldMeta.placeholder}
                                          autoComplete="current-password"
                                       />
                                    </Form.Item>
                                 );
                              })
                           )}
                        </Space>
                     </Space>
                  </Col>
               </Row>
            </Form>
         </Modal>
      </>
   );
});

ModelProviderSettingsPanel.displayName = "ModelProviderSettingsPanel";

export default ModelProviderSettingsPanel;
