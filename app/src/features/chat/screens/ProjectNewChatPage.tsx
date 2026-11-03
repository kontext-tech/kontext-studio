import PageContainer from "@/components/layout/SeoPageContainer";
import ProjectChatInputArea from "@/features/chat/components/ProjectChatInputArea";
import ChatSessionComposerControls from "@/features/chat/components/ChatSessionComposerControls";
import { useCatalogScope } from "@/features/chat/hooks/useCatalogScope";
import { useCatalogSyncPolling } from "@/features/projects/hooks/useCatalogSyncPolling";
import {
   getReadinessDescription,
   getReadinessStatusFor
} from "@/features/projects/components/data-sources/presentation";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { FileCard } from "@ant-design/x";
import { formatFileSize } from "@kontext-labs/common";
import { CommonRoleGroups, PermissionButton } from "@kontext-labs/auth";
import {
   ChatUploadPreparationService,
   useChat,
   useChatSessionStore,
   useChatSessionStoreApi,
   useFoundationModels
} from "@kontext-labs/chat";
import {
   DatabaseOutlined,
   PlusOutlined,
   TagOutlined
} from "@kontext-labs/icons";
import { useUser } from "@kontext-labs/identity";
import { useProject } from "@kontext-labs/project";
import {
   type ChatUploadPreparationFailure,
   type ChatUploadPreparationStatus,
   FileFormatType,
   type ProjectConfiguration,
   type ProjectModel,
   type StartChatUploadPreparationResponse
} from "@kontext-labs/schema";
import { useDataService } from "@kontext-labs/app-runtime/hooks";
import { LoadingSpinner, useUiApp } from "@kontext-labs/ui";
import {
   Alert,
   Button,
   Card,
   Flex,
   Layout,
   Modal,
   Select,
   Space,
   Tabs,
   Tag,
   theme,
   Typography
} from "antd";
import {
   useEffect,
   useMemo,
   useRef,
   useState,
   type CSSProperties,
   type ChangeEvent
} from "react";
import { useNavigate } from "react-router-dom";

const { Content } = Layout;
const { useToken } = theme;

const CATALOG_PROVIDER_LABELS: Record<string, string> = {
   iceberg_internal: "Internal Iceberg",
   duckdb_external: "DuckDB",
   mysql_external: "MySQL",
   oracle_external: "Oracle",
   postgresql_external: "PostgreSQL",
   sqlserver_external: "SQL Server",
   teradata_external: "Teradata",
   sqlite_external: "SQLite"
};

interface SelectableCardProps {
   title: string;
   subtitle?: string;
   description?: string;
   selected: boolean;
   disabled?: boolean;
   onClick: () => void;
   badge?: React.ReactNode;
   action?: React.ReactNode;
}

const SelectableCard = ({
   title,
   subtitle,
   description,
   selected,
   disabled = false,
   onClick,
   badge,
   action
}: SelectableCardProps) => {
   const { token } = useToken();

   return (
      <Card
         size="small"
         hoverable
         style={{
            minWidth: 220,
            maxWidth: 280,
            cursor: disabled ? "not-allowed" : "pointer",
            borderColor: selected ? token.colorPrimary : token.colorBorder,
            boxShadow: selected ? token.boxShadowSecondary : "none",
            opacity: disabled ? 0.6 : 1
         }}
         onClick={disabled ? undefined : onClick}
         styles={{ body: { padding: 14 } }}
      >
         <Flex vertical gap={10}>
            <Flex justify="space-between" align="flex-start" gap="small">
               <Flex vertical gap={4} style={{ minWidth: 0 }}>
                  <Typography.Text strong ellipsis>
                     {title}
                  </Typography.Text>
                  {subtitle && (
                     <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {subtitle}
                     </Typography.Text>
                  )}
               </Flex>
               {badge}
            </Flex>
            {description && (
               <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {description}
               </Typography.Text>
            )}
            {action && (
               <div onClick={(event) => event.stopPropagation()}>{action}</div>
            )}
         </Flex>
      </Card>
   );
};

const getCatalogProviderLabel = (providerKind?: string) =>
   CATALOG_PROVIDER_LABELS[providerKind ?? ""] || providerKind || "Data Source";

const CHAT_PREPARATION_POLL_INTERVAL_MS = 1500;
const CHAT_PREPARATION_MAX_POLL_DURATION_MS = 10 * 60 * 1000;
const MAX_STAGED_CHAT_ATTACHMENTS = 10;
const CHAT_UPLOAD_OVERWRITE_CONFLICT_CODE = "already_exists";
const TERMINAL_CHAT_PREPARATION_STATUSES = new Set([
   "succeeded",
   "failed",
   "cancelled",
   "timed_out"
]);
const CHAT_DATA_FILE_TYPES = new Set<FileFormatType>([
   FileFormatType.CSV,
   FileFormatType.TSV,
   FileFormatType.Parquet,
   FileFormatType.JSON,
   FileFormatType.JSONL,
   FileFormatType.Excel
]);

interface StagedChatAttachment {
   id: string;
   file: File;
   fileType: FileFormatType;
}

const getChatUploadableFileTypes = (configuration: ProjectConfiguration) =>
   configuration.allowedFileTypes.filter((fileType) =>
      CHAT_DATA_FILE_TYPES.has(fileType.fileFormatType)
   );

const getFileExtension = (filename: string) =>
   filename.toLowerCase().match(/\.[^.]+$/)?.[0] || "";

const summarizeChatPreparationFailures = (
   failures: ChatUploadPreparationFailure[]
) => {
   if (failures.length === 0) {
      return "";
   }

   const labels = failures
      .map((failure) => failure.filename || failure.fileId || "Unnamed file")
      .slice(0, 3);
   const remainingCount = failures.length - labels.length;
   return remainingCount > 0
      ? `${labels.join(", ")} and ${remainingCount} more`
      : labels.join(", ");
};

const isOverwriteConflictFailure = (failure: ChatUploadPreparationFailure) =>
   failure.code === CHAT_UPLOAD_OVERWRITE_CONFLICT_CODE ||
   failure.error.toLowerCase().includes("allow overwrite");

interface ProjectNewChatContentProps {
   project: ProjectModel;
}

const ProjectNewChatContent = ({ project }: ProjectNewChatContentProps) => {
   const { token } = useToken();
   const { user } = useUser();
   const { getRoutePath } = useRoute();
   const navigate = useNavigate();
   const apiErrorHandler = useApiErrorHandler();
   const { message: messageApi, modal } = useUiApp();
   const chatUploadPreparationService = useDataService(
      ChatUploadPreparationService,
      apiErrorHandler
   );

   const [isScopeCustomizationOpen, setIsScopeCustomizationOpen] =
      useState(false);
   const [isPinTableOpen, setIsPinTableOpen] = useState(false);
   const [activeCatalogProvider, setActiveCatalogProvider] = useState<string>();
   const [stagedAttachments, setStagedAttachments] = useState<
      StagedChatAttachment[]
   >([]);
   const [isPreparingAttachments, setIsPreparingAttachments] = useState(false);
   const [, setPreparationStatus] =
      useState<ChatUploadPreparationStatus | null>(null);
   const [preparationNotice, setPreparationNotice] = useState<{
      type: "error" | "warning" | "info";
      title: string;
      description?: string;
   } | null>(null);
   const fileInputRef = useRef<HTMLInputElement | null>(null);
   const isMountedRef = useRef(true);

   useEffect(() => {
      isMountedRef.current = true;
      return () => {
         isMountedRef.current = false;
      };
   }, []);

   const closeScopeCustomizationModal = () => {
      setIsScopeCustomizationOpen(false);
      setIsPinTableOpen(false);
   };

   const displayName = user?.firstName || "there";
   const gradientStyle = {
      ["--gradient-start"]: token.colorPrimary,
      ["--gradient-end"]: token.colorInfo
   } as CSSProperties;

   const {
      connections,
      namespaces,
      entities,
      selectedConnectionId,
      selectedNamespace,
      selectedEntityId,
      selectedConnection,
      selectedEntity,
      isCatalogLoading,
      isEntitiesLoading,
      hasLoadedEntities,
      catalogError,
      loadEntities,
      refreshCatalogScope,
      clearEntitySelection,
      selectConnection,
      selectNamespace,
      selectEntity
   } = useCatalogScope(project, apiErrorHandler);

   const selectedModelSelectionId = useChatSessionStore(
      (state) => state.modelSelectionId
   );
   const chatSessionStoreApi = useChatSessionStoreApi();
   const setSelectedModelSelectionId = useChatSessionStore(
      (state) => state.setModelSelectionId
   );

   const { data: modelCatalog = [] } = useFoundationModels(apiErrorHandler);

   const {
      sendMessage,
      isAvailable,
      chatSession,
      createChatSession,
      deleteChatSession,
      error
   } = useChat(project, {
      errorHandler: apiErrorHandler
   });

   useEffect(() => {
      if (modelCatalog.length > 0 && !selectedModelSelectionId) {
         setSelectedModelSelectionId(modelCatalog[0].selectionId);
      }
   }, [modelCatalog, selectedModelSelectionId, setSelectedModelSelectionId]);

   useEffect(() => {
      if (!isPinTableOpen || hasLoadedEntities || !selectedNamespace) {
         return;
      }

      void loadEntities();
   }, [hasLoadedEntities, isPinTableOpen, loadEntities, selectedNamespace]);

   useCatalogSyncPolling(connections, refreshCatalogScope);

   const effectiveModelSelectionId =
      selectedModelSelectionId || modelCatalog[0]?.selectionId;
   const chatUploadableFileTypes = useMemo(
      () => getChatUploadableFileTypes(project.configuration),
      [project.configuration]
   );
   const chatAttachmentAccept = chatUploadableFileTypes
      .map((fileType) => fileType.fileExtension)
      .join(",");
   const hasChatAttachmentSupport = chatUploadableFileTypes.length > 0;
   const areAttachmentsStaged = stagedAttachments.length > 0;

   const openAttachmentPicker = () => {
      if (!hasChatAttachmentSupport || isPreparingAttachments) {
         return;
      }

      fileInputRef.current?.click();
   };

   const clearStagedAttachments = () => {
      setStagedAttachments([]);
      setPreparationStatus(null);
      setPreparationNotice(null);
   };

   const removeStagedAttachment = (attachmentId: string) => {
      setStagedAttachments((current) =>
         current.filter((attachment) => attachment.id !== attachmentId)
      );
      setPreparationStatus(null);
      setPreparationNotice(null);
   };

   const handleAttachmentInputChange = (
      event: ChangeEvent<HTMLInputElement>
   ) => {
      const selectedFiles = Array.from(event.target.files ?? []);
      event.target.value = "";

      if (selectedFiles.length === 0) {
         return;
      }

      const allowedTypesByExtension = new Map(
         chatUploadableFileTypes.map((fileType) => [
            fileType.fileExtension.toLowerCase(),
            fileType
         ])
      );
      const nextAttachmentsByName = new Map(
         stagedAttachments.map((attachment) => [
            attachment.file.name.toLowerCase(),
            attachment
         ])
      );
      const validationErrors: string[] = [];

      selectedFiles.forEach((file) => {
         const fileExtension = getFileExtension(file.name);
         const matchingFileType = allowedTypesByExtension.get(fileExtension);
         if (!matchingFileType) {
            validationErrors.push(`${file.name} can't be attached to chat.`);
            return;
         }

         if (file.size > project.configuration.maxFileBytesSize) {
            validationErrors.push(
               `${file.name} exceeds ${formatFileSize(project.configuration.maxFileBytesSize)}.`
            );
            return;
         }

         const fileKey = file.name.toLowerCase();
         const isReplacement = nextAttachmentsByName.has(fileKey);
         if (
            !isReplacement &&
            nextAttachmentsByName.size >= MAX_STAGED_CHAT_ATTACHMENTS
         ) {
            validationErrors.push(
               `You can attach up to ${MAX_STAGED_CHAT_ATTACHMENTS} files before starting chat.`
            );
            return;
         }

         nextAttachmentsByName.set(fileKey, {
            id: `${file.name}-${file.lastModified}-${file.size}`,
            file,
            fileType: matchingFileType.fileFormatType
         });
      });

      setStagedAttachments(Array.from(nextAttachmentsByName.values()));
      setPreparationStatus(null);
      setPreparationNotice(null);
      if (isScopeCustomizationOpen) {
         closeScopeCustomizationModal();
      }

      if (validationErrors.length === 0) {
         return;
      }

      if (validationErrors.length === 1) {
         messageApi.warning(validationErrors[0]);
         return;
      }

      modal.warning({
         title: "Some files couldn't be attached",
         width: 520,
         content: (
            <Flex vertical gap={4}>
               {validationErrors.map((errorText) => (
                  <Typography.Text key={errorText}>{errorText}</Typography.Text>
               ))}
            </Flex>
         )
      });
   };

   const pollChatUploadPreparation = async (
      runId: string
   ): Promise<ChatUploadPreparationStatus> => {
      const deadline = Date.now() + CHAT_PREPARATION_MAX_POLL_DURATION_MS;

      while (true) {
         const statusResult =
            await chatUploadPreparationService.getUploadPreparationStatus(
               project.id,
               runId
            );
         if (!statusResult.succeed || !statusResult.data) {
            throw new Error(
               statusResult.error?.messages?.[0] ||
                  statusResult.error?.title ||
                  "Failed to load attachment preparation status."
            );
         }

         if (!isMountedRef.current) {
            throw new Error("Attachment preparation was cancelled.");
         }

         setPreparationStatus(statusResult.data);
         if (TERMINAL_CHAT_PREPARATION_STATUSES.has(statusResult.data.status)) {
            return statusResult.data;
         }

         if (Date.now() >= deadline) {
            throw new Error(
               "Timed out while preparing the attached files for chat. Please try again."
            );
         }

         await new Promise<void>((resolve) => {
            window.setTimeout(resolve, CHAT_PREPARATION_POLL_INTERVAL_MS);
         });
      }
   };

   const confirmOverwriteAttachments = async (
      failures: ChatUploadPreparationFailure[]
   ) =>
      new Promise<boolean>((resolve) => {
         const filenames = failures
            .map((failure) => failure.filename)
            .filter((filename): filename is string => Boolean(filename));

         modal.confirm({
            title:
               filenames.length === 1
                  ? "Replace the existing file?"
                  : "Replace the existing files?",
            okText: filenames.length === 1 ? "Replace file" : "Replace files",
            cancelText: "Cancel",
            content: (
               <Flex vertical gap={8}>
                  <Typography.Text>
                     These files already exist here. Replace them and use the
                     latest versions in this chat?
                  </Typography.Text>
                  {filenames.length > 0 ? (
                     <Flex vertical gap={4}>
                        {filenames.map((filename) => (
                           <Typography.Text key={filename} type="secondary">
                              {filename}
                           </Typography.Text>
                        ))}
                     </Flex>
                  ) : null}
               </Flex>
            ),
            onOk: async () => {
               resolve(true);
            },
            onCancel: () => {
               resolve(false);
            }
         });
      });

   const handleSendMessage = async (
      message: string,
      context?: {
         pythonExecutionApprovalMode?: "always_ask" | "auto_approve";
      }
   ) => {
      if (!isAvailable) {
         return;
      }

      if (!chatSession?.id) {
         const sessionName = `Chat - ${new Date().toLocaleString()}`;
         if (areAttachmentsStaged) {
            let notice: {
               type: "error" | "warning" | "info";
               title: string;
               description?: string;
            } | null = null;

            setPreparationNotice(null);
            setIsPreparingAttachments(true);
            setPreparationStatus({
               runId: "00000000-0000-0000-0000-000000000000",
               status: "starting",
               progress: 0,
               internalCatalogConnectionId: null,
               readyFileIds: [],
               failedFiles: [],
               steps: []
            });

            try {
               const requestPreparation = async (allowOverwrite = false) => {
                  const startResult =
                     await chatUploadPreparationService.startUploadPreparation(
                        project.id,
                        stagedAttachments.map((attachment) => attachment.file),
                        allowOverwrite
                     );
                  if (!startResult.succeed || !startResult.data) {
                     throw new Error(
                        startResult.error?.messages?.[0] ||
                           startResult.error?.title ||
                           "We couldn't start preparing your files."
                     );
                  }
                  return startResult.data;
               };

               const applyPreparationStartState = (
                  startData: StartChatUploadPreparationResponse
               ) => {
                  setPreparationStatus({
                     runId: startData.runId,
                     status: startData.successCount > 0 ? "starting" : "failed",
                     progress: 0,
                     internalCatalogConnectionId:
                        startData.internalCatalogConnectionId || null,
                     readyFileIds: [],
                     failedFiles: startData.uploadErrors,
                     steps: []
                  });
               };

               let startData = await requestPreparation();
               const overwriteConflicts = startData.uploadErrors.filter(
                  isOverwriteConflictFailure
               );
               if (
                  startData.successCount === 0 &&
                  overwriteConflicts.length > 0 &&
                  overwriteConflicts.length === startData.uploadErrors.length
               ) {
                  setIsPreparingAttachments(false);
                  setPreparationStatus(null);

                  const shouldOverwrite =
                     await confirmOverwriteAttachments(overwriteConflicts);
                  if (!shouldOverwrite) {
                     notice = {
                        type: "warning",
                        title: "These files already exist",
                        description:
                           "Replace the existing files to use the latest versions in chat, or rename them first."
                     };
                     setPreparationNotice(notice);
                     throw new Error(notice.description || notice.title);
                  }

                  setPreparationNotice(null);
                  setIsPreparingAttachments(true);
                  setPreparationStatus({
                     runId: "00000000-0000-0000-0000-000000000000",
                     status: "starting",
                     progress: 0,
                     internalCatalogConnectionId: null,
                     readyFileIds: [],
                     failedFiles: [],
                     steps: []
                  });
                  startData = await requestPreparation(true);
               }

               applyPreparationStartState(startData);

               const finalStatus = await pollChatUploadPreparation(
                  startData.runId
               );
               const effectiveConnectionId =
                  finalStatus.internalCatalogConnectionId ||
                  startData.internalCatalogConnectionId;

               if (!effectiveConnectionId) {
                  throw new Error(
                     "We couldn't start chat with the attached files."
                  );
               }

               if (finalStatus.readyFileIds.length === 0) {
                  notice = {
                     type: "error",
                     title: "Your files couldn't be prepared for chat",
                     description:
                        finalStatus.failedFiles.length > 0
                           ? `We couldn't get these files ready: ${summarizeChatPreparationFailures(finalStatus.failedFiles)}.`
                           : "We couldn't get the attached files ready for chat."
                  };
                  setPreparationNotice(notice);
                  throw new Error(notice.description || notice.title);
               }

               const newSession = await createChatSession(
                  sessionName,
                  effectiveModelSelectionId,
                  {
                     defaultCatalogConnectionId: effectiveConnectionId,
                     ...(context?.pythonExecutionApprovalMode
                        ? {
                             pythonExecutionApprovalMode:
                                context.pythonExecutionApprovalMode
                          }
                        : {})
                  }
               );
               if (!newSession) {
                  throw new Error("Failed to create chat session.");
               }

               const seedResult =
                  await chatUploadPreparationService.seedChatAttachmentContext(
                     project.id,
                     newSession.id,
                     startData.runId
                  );
               if (!seedResult.succeed) {
                  await deleteChatSession(newSession.id);
                  chatSessionStoreApi.getState().clearActiveSession();
                  throw new Error(
                     seedResult.error?.messages?.[0] ||
                        seedResult.error?.title ||
                        "We couldn't finish preparing the attached files for chat."
                  );
               }

               const uploadPreparationWarning =
                  finalStatus.failedFiles.length > 0
                     ? `Your chat started with ${finalStatus.readyFileIds.length} attached file${finalStatus.readyFileIds.length === 1 ? "" : "s"} ready to use. Some files couldn't be prepared: ${summarizeChatPreparationFailures(finalStatus.failedFiles)}.`
                     : undefined;
               const path = getRoutePath(
                  RouteNames.PROJECT_CHAT_SESSION_DETAIL,
                  project,
                  {
                     sessionId: newSession.id
                  }
               );

               setStagedAttachments([]);
               setPreparationStatus(null);
               setPreparationNotice(null);
               navigate(path, {
                  state: {
                     initialMessage: message,
                     uploadPreparationWarning
                  }
               });
               return;
            } catch (error) {
               if (!notice) {
                  notice = {
                     type: "error",
                     title: "We couldn't get your files ready",
                     description:
                        error instanceof Error
                           ? error.message
                           : "We couldn't get your files ready for chat."
                  };
                  setPreparationNotice(notice);
               }
               throw error;
            } finally {
               setIsPreparingAttachments(false);
            }
         }

         const newSession = await createChatSession(
            sessionName,
            effectiveModelSelectionId,
            {
               defaultCatalogConnectionId: selectedConnectionId,
               ...(selectedNamespace
                  ? { defaultNamespace: selectedNamespace }
                  : {}),
               ...(selectedEntityId
                  ? { defaultEntityId: selectedEntityId }
                  : {}),
               ...(context?.pythonExecutionApprovalMode
                  ? {
                       pythonExecutionApprovalMode:
                          context.pythonExecutionApprovalMode
                    }
                  : {})
            }
         );

         if (newSession) {
            const path = getRoutePath(
               RouteNames.PROJECT_CHAT_SESSION_DETAIL,
               project,
               {
                  sessionId: newSession.id
               }
            );
            navigate(path, {
               state: {
                  initialMessage: message
               }
            });
         }
         return;
      }

      await sendMessage(message);
   };

   const isInitialCatalogLoad = isCatalogLoading && connections.length === 0;
   const scopeSummaryParts = [
      selectedConnection?.displayName,
      selectedNamespace,
      selectedEntity?.displayName || selectedEntity?.entityName
   ].filter(Boolean);
   const scopeSummary = scopeSummaryParts.join(" / ");
   const catalogProviderTabs = useMemo(
      () =>
         Array.from(
            new Set(connections.map((connection) => connection.providerKind))
         )
            .filter(Boolean)
            .map((providerKind) => ({
               key: providerKind,
               label: getCatalogProviderLabel(providerKind)
            })),
      [connections]
   );
   const effectiveCatalogProvider =
      activeCatalogProvider ||
      selectedConnection?.providerKind ||
      catalogProviderTabs[0]?.key;
   const visibleConnections = connections.filter(
      (connection) => connection.providerKind === effectiveCatalogProvider
   );
   const namespaceOptions = useMemo(
      () =>
         namespaces.map((namespace) => ({
            label: namespace.displayName || namespace.name,
            value: namespace.name,
            description:
               namespace.entityCount > 0
                  ? `${namespace.entityCount} table${
                       namespace.entityCount === 1 ? "" : "s"
                    }`
                  : "Namespace"
         })),
      [namespaces]
   );
   const configuredNamespace = selectedConnection?.config?.defaultNamespace;
   const attachmentButtonLabel =
      stagedAttachments.length > 0 ? "Attach more files" : "Attach files";
   const stagedAttachmentCardItems = useMemo(
      () =>
         stagedAttachments.map((attachment) => ({
            key: attachment.id,
            name: attachment.file.name,
            byte: attachment.file.size,
            description: false
         })),
      [stagedAttachments]
   );
   const preparationBanner = isPreparingAttachments ? (
      <Flex align="center" gap={8} style={{ minHeight: 24 }}>
         <LoadingSpinner size="small" />
         <Typography.Text type="secondary">
            Preparing your files...
         </Typography.Text>
      </Flex>
   ) : preparationNotice ? (
      <Alert
         type={preparationNotice.type}
         showIcon
         message={preparationNotice.title}
         description={preparationNotice.description}
      />
   ) : null;

   return (
      <>
         <Layout
            style={{
               height: "100%",
               overflow: "hidden",
               background: token.colorBgContainer
            }}
         >
            <Content
               style={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                  background: token.colorBgContainer
               }}
            >
               {isInitialCatalogLoad ? (
                  <Flex
                     vertical
                     align="center"
                     justify="center"
                     style={{ flex: 1, padding: 24 }}
                     gap="middle"
                  >
                     <LoadingSpinner />
                     <Typography.Text type="secondary">
                        Loading available sources...
                     </Typography.Text>
                  </Flex>
               ) : (
                  <div
                     style={{
                        flex: 1,
                        minHeight: 0,
                        overflowY: "auto",
                        padding: 24
                     }}
                  >
                     <div
                        style={{
                           maxWidth: 960,
                           margin: "0 auto",
                           minHeight: "100%",
                           display: "flex",
                           flexDirection: "column",
                           justifyContent: "center"
                        }}
                     >
                        <div
                           style={{
                              maxWidth: 840,
                              margin: "0 auto",
                              width: "100%"
                           }}
                        >
                           <div
                              style={{
                                 maxWidth: 720,
                                 margin: "0 auto",
                                 textAlign: "center"
                              }}
                           >
                              <Typography.Title level={2}>
                                 Hello,{" "}
                                 <span
                                    className="gradient-text"
                                    style={gradientStyle}
                                 >
                                    {displayName}
                                 </span>
                              </Typography.Title>
                              <Typography.Paragraph
                                 type="secondary"
                                 style={{
                                    marginBottom: 12,
                                    fontSize: 15
                                 }}
                              >
                                 Start with a prompt, attach files to ask
                                 questions about them, or pick a connected
                                 source.
                              </Typography.Paragraph>
                           </div>

                           {catalogError && (
                              <Alert
                                 title="Data source sync issue"
                                 description={catalogError}
                                 type="warning"
                                 showIcon
                                 style={{
                                    maxWidth: 880,
                                    margin: "24px auto 0"
                                 }}
                              />
                           )}

                           {error && (
                              <Alert
                                 title="Unable to start chat"
                                 description={error}
                                 type="error"
                                 showIcon
                                 style={{
                                    maxWidth: 880,
                                    margin: "24px auto 0"
                                 }}
                              />
                           )}

                           <div
                              style={{ maxWidth: 880, margin: "20px auto 0" }}
                           >
                              <input
                                 ref={fileInputRef}
                                 type="file"
                                 multiple
                                 accept={chatAttachmentAccept}
                                 style={{ display: "none" }}
                                 onChange={handleAttachmentInputChange}
                              />
                              <ProjectChatInputArea
                                 foundationModels={modelCatalog}
                                 modelSelectionId={effectiveModelSelectionId}
                                 showWarning={true}
                                 isBusy={isPreparingAttachments}
                                 onSubmitMessage={handleSendMessage}
                                 statusBanner={preparationBanner}
                                 preSessionLeadingAction={
                                    hasChatAttachmentSupport ? (
                                       <PermissionButton
                                          size="small"
                                          type="text"
                                          title={attachmentButtonLabel}
                                          aria-label="Attach files"
                                          icon={<PlusOutlined />}
                                          onClick={openAttachmentPicker}
                                          disabled={isPreparingAttachments}
                                          allowedProjectRoles={
                                             CommonRoleGroups.CONTENT_EDITORS
                                          }
                                          tooltipWhenEnabled="Attach files to query them in chat"
                                          tooltipWhenDisabled="You need contributor permissions to attach files"
                                       />
                                    ) : (
                                       <Button
                                          size="small"
                                          type="text"
                                          disabled
                                          title="File attachments aren't available for this project"
                                          aria-label="Attach files"
                                          icon={<PlusOutlined />}
                                       />
                                    )
                                 }
                                 stagedAttachmentTray={({ hasInput }) =>
                                    areAttachmentsStaged ? (
                                       <Flex vertical gap={6}>
                                          <FileCard.List
                                             items={stagedAttachmentCardItems}
                                             size="small"
                                             overflow="wrap"
                                             removable={!isPreparingAttachments}
                                             onRemove={(item) => {
                                                if (
                                                   typeof item.key === "string"
                                                ) {
                                                   removeStagedAttachment(
                                                      item.key
                                                   );
                                                }
                                             }}
                                             styles={{
                                                root: {
                                                   marginBottom: 0
                                                },
                                                card: {
                                                   minWidth: 180,
                                                   maxWidth: 240
                                                }
                                             }}
                                          />
                                          {stagedAttachments.length > 1 ? (
                                             <Flex justify="flex-end">
                                                <Button
                                                   size="small"
                                                   type="link"
                                                   onClick={
                                                      clearStagedAttachments
                                                   }
                                                   disabled={
                                                      isPreparingAttachments
                                                   }
                                                   style={{ paddingInline: 0 }}
                                                >
                                                   Clear all
                                                </Button>
                                             </Flex>
                                          ) : null}
                                          {!hasInput ? (
                                             <Typography.Text
                                                type="secondary"
                                                style={{ fontSize: 12 }}
                                             >
                                                Add a question to send these
                                                files.
                                             </Typography.Text>
                                          ) : null}
                                       </Flex>
                                    ) : null
                                 }
                                 sessionSettingsAccessory={({
                                    disabled,
                                    pythonExecutionApprovalMode,
                                    onPythonExecutionApprovalModeChange
                                 }) => (
                                    <ChatSessionComposerControls
                                       disabled={
                                          disabled || isPreparingAttachments
                                       }
                                       pythonExecutionApprovalMode={
                                          pythonExecutionApprovalMode
                                       }
                                       onPythonExecutionApprovalModeChange={
                                          onPythonExecutionApprovalModeChange
                                       }
                                    />
                                 )}
                                 contextAccessory={
                                    areAttachmentsStaged ? null : (
                                       <Button
                                          size="small"
                                          type="text"
                                          icon={<DatabaseOutlined />}
                                          onClick={() =>
                                             setIsScopeCustomizationOpen(true)
                                          }
                                          style={{
                                             color: token.colorTextSecondary,
                                             maxWidth: 260,
                                             display: "inline-flex",
                                             alignItems: "center",
                                             fontSize: token.fontSizeSM,
                                             height: 24,
                                             paddingInline: 4
                                          }}
                                       >
                                          <span
                                             style={{
                                                display: "block",
                                                minWidth: 0,
                                                overflow: "hidden",
                                                textOverflow: "ellipsis",
                                                whiteSpace: "nowrap"
                                             }}
                                          >
                                             {scopeSummary ||
                                                selectedConnection?.displayName ||
                                                "Connected source"}
                                          </span>
                                       </Button>
                                    )
                                 }
                              />
                           </div>
                        </div>
                     </div>
                  </div>
               )}
            </Content>
         </Layout>

         <Modal
            title="Choose Connected Source"
            open={isScopeCustomizationOpen && !areAttachmentsStaged}
            onCancel={closeScopeCustomizationModal}
            footer={
               <Button type="primary" onClick={closeScopeCustomizationModal}>
                  Done
               </Button>
            }
         >
            <Space
               orientation="vertical"
               size="large"
               style={{ width: "100%" }}
            >
               <div>
                  <Typography.Text strong>Connected Source</Typography.Text>
                  <Typography.Paragraph
                     type="secondary"
                     style={{ marginBottom: 0 }}
                  >
                     Pick a connected source for this chat, then optionally
                     narrow it to a schema or table.
                  </Typography.Paragraph>
               </div>

               {catalogProviderTabs.length > 0 && (
                  <div>
                     <Tabs
                        activeKey={effectiveCatalogProvider}
                        onChange={setActiveCatalogProvider}
                        items={catalogProviderTabs}
                     />
                     <div
                        style={{
                           display: "flex",
                           gap: 12,
                           overflowX: "auto",
                           paddingBottom: 4
                        }}
                     >
                        {visibleConnections.map((connection) => {
                           const isSelected =
                              selectedConnectionId === connection.id;
                           const readiness = getReadinessStatusFor(
                              connection.readinessReason,
                              connection.isQueryReady,
                              { distinguishQueued: true }
                           );

                           return (
                              <SelectableCard
                                 key={connection.id}
                                 title={connection.displayName}
                                 subtitle={
                                    connection.description ||
                                    getCatalogProviderLabel(
                                       connection.providerKind
                                    )
                                 }
                                 description={
                                    isSelected && scopeSummary
                                       ? `Current scope: ${scopeSummary}`
                                       : getReadinessDescription(connection)
                                 }
                                 selected={isSelected}
                                 disabled={!connection.isQueryReady}
                                 badge={
                                    <Tag color={readiness.color}>
                                       {readiness.label}
                                    </Tag>
                                 }
                                 onClick={() => {
                                    if (
                                       connection.id &&
                                       connection.isQueryReady
                                    ) {
                                       void selectConnection(connection.id);
                                       setIsPinTableOpen(false);
                                    }
                                 }}
                              />
                           );
                        })}
                     </div>
                  </div>
               )}

               <div>
                  <Flex
                     justify="space-between"
                     align="center"
                     wrap
                     gap="small"
                     style={{ marginBottom: 8 }}
                  >
                     <div>
                        <Typography.Text strong>
                           Namespace Override
                        </Typography.Text>
                        <Typography.Paragraph
                           type="secondary"
                           style={{ marginBottom: 0 }}
                        >
                           Optional. Leave blank to chat across the selected
                           data source.
                        </Typography.Paragraph>
                     </div>
                     {(selectedNamespace || configuredNamespace) && (
                        <Typography.Text
                           type="secondary"
                           style={{ fontSize: 12 }}
                        >
                           {selectedNamespace
                              ? "Custom namespace selected"
                              : `Configured default available: ${configuredNamespace}`}
                        </Typography.Text>
                     )}
                  </Flex>

                  <Select
                     allowClear
                     showSearch
                     size="large"
                     placeholder={
                        selectedConnection?.isQueryReady
                           ? "Choose a namespace"
                           : "Select a ready data source first"
                     }
                     value={selectedNamespace}
                     style={{ width: "100%" }}
                     optionFilterProp="label"
                     options={namespaceOptions}
                     optionRender={(option) => (
                        <div style={{ padding: "4px 0" }}>
                           <div style={{ fontWeight: 500 }}>
                              {option.data.label}
                           </div>
                           <div
                              style={{
                                 fontSize: 12,
                                 lineHeight: 1.4,
                                 opacity: 0.7
                              }}
                           >
                              {String(option.data.description)}
                           </div>
                        </div>
                     )}
                     onChange={(value) => {
                        void selectNamespace(
                           typeof value === "string" ? value : undefined
                        );
                        setIsPinTableOpen(false);
                     }}
                     disabled={!selectedConnection?.isQueryReady}
                  />
               </div>

               <div>
                  <Flex
                     justify="space-between"
                     align="center"
                     wrap
                     gap="small"
                     style={{ marginBottom: 8 }}
                  >
                     <div>
                        <Typography.Text strong>Table Override</Typography.Text>
                        <Typography.Paragraph
                           type="secondary"
                           style={{ marginBottom: 0 }}
                        >
                           Optional. Pin a single table only after choosing a
                           namespace.
                        </Typography.Paragraph>
                     </div>
                     <Space size="small">
                        {selectedEntityId && (
                           <Button type="link" onClick={clearEntitySelection}>
                              Clear pinned table
                           </Button>
                        )}
                        <Button
                           size="small"
                           icon={<TagOutlined />}
                           onClick={() => setIsPinTableOpen((open) => !open)}
                           disabled={
                              !selectedNamespace ||
                              !selectedConnection?.isQueryReady
                           }
                        >
                           {isPinTableOpen ? "Hide table pin" : "Pin a table"}
                        </Button>
                     </Space>
                  </Flex>

                  {isPinTableOpen && (
                     <Select
                        allowClear
                        showSearch
                        size="large"
                        placeholder={
                           isEntitiesLoading
                              ? "Loading tables..."
                              : "Select a table to pin"
                        }
                        value={selectedEntityId}
                        loading={isEntitiesLoading}
                        style={{ width: "100%" }}
                        optionFilterProp="label"
                        options={entities.map((entity) => ({
                           label: entity.displayName || entity.entityName,
                           value: entity.id,
                           description: `${entity.namespaceName}.${entity.entityName}`
                        }))}
                        optionRender={(option) => (
                           <div style={{ padding: "4px 0" }}>
                              <div style={{ fontWeight: 500 }}>
                                 {option.data.label}
                              </div>
                              <div
                                 style={{
                                    fontSize: 12,
                                    lineHeight: 1.4,
                                    opacity: 0.7
                                 }}
                              >
                                 {String(option.data.description)}
                              </div>
                           </div>
                        )}
                        notFoundContent={
                           isEntitiesLoading ? (
                              <LoadingSpinner />
                           ) : (
                              "No tables found in this namespace"
                           )
                        }
                        onDropdownVisibleChange={(open) => {
                           if (
                              open &&
                              selectedNamespace &&
                              !hasLoadedEntities &&
                              !isEntitiesLoading
                           ) {
                              void loadEntities();
                           }
                        }}
                        onChange={(value) =>
                           selectEntity(
                              typeof value === "string" ? value : undefined
                           )
                        }
                     />
                  )}
               </div>
            </Space>
         </Modal>
      </>
   );
};

const ProjectNewChatPage = () => {
   const { currentProject } = useProject();

   if (!currentProject) {
      return null;
   }

   return (
      <PageContainer
         key={`project-new-chat-${currentProject.id}`}
         title="New Chat"
         routeName={RouteNames.PROJECT}
         project={currentProject}
         showBreadcrumb={false}
         showPageTitle={false}
         fluid={true}
         style={{ height: "100%" }}
      >
         <ProjectNewChatContent project={currentProject} />
      </PageContainer>
   );
};

export default ProjectNewChatPage;
