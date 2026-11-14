import PageContainer from "@/components/layout/SeoPageContainer";
import ChatSessionComposerControls from "@/features/chat/components/ChatSessionComposerControls";
import { ChatScopeCustomizationModal } from "@/features/chat/components/ChatScopeCustomizationModal";
import ProjectChatInputArea from "@/features/chat/components/ProjectChatInputArea";
import {
   type ChatAttachmentDeps,
   useChatAttachmentPreparation
} from "@/features/chat/hooks/useChatAttachmentPreparation";
import { useCatalogScope } from "@/features/chat/hooks/useCatalogScope";
import { useCatalogSyncPolling } from "@/features/projects/hooks/useCatalogSyncPolling";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { FileCard } from "@ant-design/x";
import { CommonRoleGroups, PermissionButton } from "@kontext-tech/auth";
import {
   useChat,
   useChatSessionStore,
   useFoundationModels
} from "@kontext-tech/chat";
import { DatabaseOutlined, PlusOutlined } from "@kontext-tech/icons";
import { useUser } from "@kontext-tech/identity";
import { useProject } from "@kontext-tech/project";
import type { ProjectModel } from "@kontext-tech/schema";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Alert, Button, Flex, Layout, theme, Typography } from "antd";
import { useEffect, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";

const { Content } = Layout;
const { useToken } = theme;

interface ProjectNewChatContentProps {
   project: ProjectModel;
}

const ProjectNewChatContent = ({ project }: ProjectNewChatContentProps) => {
   const { token } = useToken();
   const { user } = useUser();
   const { getRoutePath } = useRoute();
   const navigate = useNavigate();
   const apiErrorHandler = useApiErrorHandler();

   const [isScopeCustomizationOpen, setIsScopeCustomizationOpen] =
      useState(false);
   const [isPinTableOpen, setIsPinTableOpen] = useState(false);

   const displayName = user?.firstName || "there";
   const gradientStyle = {
      ["--gradient-start"]: token.colorPrimary,
      ["--gradient-end"]: token.colorInfo
   } as CSSProperties;

   const closeScopeCustomizationModal = () => {
      setIsScopeCustomizationOpen(false);
      setIsPinTableOpen(false);
   };

   const scope = useCatalogScope(project, apiErrorHandler);
   const {
      connections,
      selectedConnectionId,
      selectedNamespace,
      selectedEntityId,
      selectedConnection,
      selectedEntity,
      isCatalogLoading,
      hasLoadedEntities,
      catalogError,
      loadEntities,
      refreshCatalogScope
   } = scope;

   const selectedModelSelectionId = useChatSessionStore(
      (state) => state.modelSelectionId
   );
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

   const {
      fileInputRef,
      chatAttachmentAccept,
      hasChatAttachmentSupport,
      areAttachmentsStaged,
      isPreparingAttachments,
      preparationNotice,
      stagedAttachmentCardItems,
      openAttachmentPicker,
      clearStagedAttachments,
      removeStagedAttachment,
      handleAttachmentInputChange,
      startPreparedChatSession,
      chatSessionStoreApi
   } = useChatAttachmentPreparation(project);

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
   const attachmentDeps: ChatAttachmentDeps = {
      createSessionFn: (
         sessionName: string,
         modelSelectionId?: string,
         options?: Record<string, unknown>
      ) =>
         createChatSession(
            sessionName,
            modelSelectionId,
            options as Parameters<typeof createChatSession>[2]
         ),
      deleteChatSession,
      clearActiveSession: () =>
         chatSessionStoreApi.getState().clearActiveSession()
   };

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
            await startPreparedChatSession({
               deps: attachmentDeps,
               sessionName,
               message,
               effectiveModelSelectionId,
               pythonExecutionApprovalMode: context?.pythonExecutionApprovalMode
            });
            return;
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
   const attachmentButtonLabel =
      stagedAttachmentCardItems.length > 0 ? "Attach more files" : "Attach files";
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
                                          {stagedAttachmentCardItems.length >
                                          1 ? (
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

         <ChatScopeCustomizationModal
            open={isScopeCustomizationOpen && !areAttachmentsStaged}
            onClose={closeScopeCustomizationModal}
            isPinTableOpen={isPinTableOpen}
            setIsPinTableOpen={(open: boolean) => setIsPinTableOpen(open)}
            scopeSummary={scopeSummary}
            scope={scope}
         />
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
