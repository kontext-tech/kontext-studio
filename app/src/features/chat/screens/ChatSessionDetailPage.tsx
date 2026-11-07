import ProjectChatArtifactsPanel from "@/features/chat/components/ProjectChatArtifactsPanel";
import ProjectChatInputArea from "@/features/chat/components/ProjectChatInputArea";
import ChatSessionComposerControls from "@/features/chat/components/ChatSessionComposerControls";
import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useFileService } from "@kontext-tech/file";
import {
   ChatHeader,
   ChatMessagesView,
   useChat,
   useFoundationModels,
   usePythonExecutionApprovalModal,
   type MarkdownImageBlobResolver
} from "@kontext-tech/chat";
import { CatalogService } from "@kontext-tech/project";
import { useUiApp } from "@kontext-tech/ui";
import { useProject } from "@kontext-tech/project";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { useRoute } from "@/hooks/useRoute";
import { LoadingSpinner } from "@kontext-tech/ui";

import { RouteNames } from "@/types";
import {
   useChatSessionStore,
   useChatSessionStoreApi
} from "@kontext-tech/chat";
import { DatabaseOutlined } from "@kontext-tech/icons";

import {
   type CatalogConnection,
   type ProjectModel
} from "@kontext-tech/schema";
import { Alert, Button, Flex, Layout, theme } from "antd";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

const { Content, Sider } = Layout;
const { useToken } = theme;

const ChatSessionDetailPageInternal = ({
   project
}: {
   project: ProjectModel;
}) => {
   const { token } = useToken();
   const { chatSessionId } = useParams<{
      projectCode: string;
      chatSessionId: string;
   }>();
   const { getProjectChatSessionsPath } = useRoute();
   const navigate = useNavigate();
   const location = useLocation();
   const { message } = useUiApp();
   const apiErrorHandler = useApiErrorHandler();
   const catalogService = useDataService(CatalogService, apiErrorHandler);
   const fileService = useFileService(apiErrorHandler);

   const initialMessageSentRef = React.useRef(false);
   const chatService = useChatSessionStore((state) => state.chatService);
   const chatSessionStoreApi = useChatSessionStoreApi();

   // State for model selection
   const [selectedModelSelectionId, setSelectedModelSelectionId] = useState<
      string | undefined
   >(undefined);
   const [catalogConnection, setCatalogConnection] =
      useState<CatalogConnection | null>(null);

   // Data fetching with caching
   const { data: modelCatalog = [] } = useFoundationModels(apiErrorHandler);

   // Use the custom chat hook
   const requestPythonExecutionApproval = usePythonExecutionApprovalModal();
   const {
      messages,
      sendMessage,
      isAvailable,
      chatSession,
      updateChatSession,
      loadChatSession,
      clearMessages,
      artifacts,
      isSidebarOpen,
      setSidebarOpen,
      removeArtifact,
      deleteChatSession,
      // Whether messages/session are being fetched
      isMessagesLoading,
      isOwner
   } = useChat(project, {
      sessionId: chatSessionId,
      modelSelectionId: selectedModelSelectionId,
      requestPythonExecutionApproval,
      errorHandler: apiErrorHandler
   });

   // Handle initial message from navigation state
   useEffect(() => {
      if (
         location.state?.initialMessage &&
         isAvailable &&
         chatSession?.id === chatSessionId &&
         !initialMessageSentRef.current
      ) {
         const initialMessage = location.state.initialMessage;
         const uploadPreparationWarning =
            location.state?.uploadPreparationWarning;
         initialMessageSentRef.current = true;
         if (uploadPreparationWarning) {
            message.warning(uploadPreparationWarning);
         }
         // Clear the state so it doesn't resend on refresh
         navigate(location.pathname, { replace: true, state: {} });
         sendMessage(initialMessage);
      }
   }, [
      location.state,
      isAvailable,
      chatSession?.id,
      chatSessionId,
      message,
      sendMessage,
      navigate,
      location.pathname
   ]);

   // Load the chat session on mount
   useEffect(() => {
      const load = async () => {
         if (project.id && chatSessionId) {
            if (!chatService) {
               return;
            }

            const currentSession = chatSessionStoreApi.getState().chatSession;

            // If we already have this session loaded, we might not need to reload it
            // especially if we just created it and are about to send the first message
            if (currentSession?.id === chatSessionId) {
               // Still sync the local state with the session
               setSelectedModelSelectionId(
                  currentSession.modelSelectionId || undefined
               );

               // If there are artifacts, open the sidebar
               if (chatSessionStoreApi.getState().artifacts.length > 0) {
                  setSidebarOpen(true);
               }
               return;
            }

            // Clear messages if we're switching to a different session
            // to avoid showing old content while loading
            clearMessages();

            try {
               const success = await loadChatSession(chatSessionId);
               if (success) {
                  // After loading, sync the local state with the loaded session
                  const session = chatSessionStoreApi.getState().chatSession;
                  if (session) {
                     setSelectedModelSelectionId(
                        session.modelSelectionId || undefined
                     );

                     // If there are artifacts, open the sidebar
                     if (chatSessionStoreApi.getState().artifacts.length > 0) {
                        setSidebarOpen(true);
                     }
                  }
               }
            } catch (err) {
               console.error("Failed to load chat session:", err);
               message.error("Failed to load chat session");
               navigate(getProjectChatSessionsPath(project));
            }
         }
      };
      load();
   }, [
      project,
      chatSessionId,
      chatService,
      chatSessionStoreApi,
      loadChatSession,
      navigate,
      getProjectChatSessionsPath,
      message,
      clearMessages,
      setSidebarOpen
   ]);

   // Fetch foundation models
   // Handled by useFoundationModels hook

   const displaySessionName = chatSession?.sessionName || "Chat";

   useEffect(() => {
      let cancelled = false;

      const loadCatalogConnectionName = async () => {
         const connectionId = chatSession?.defaultCatalogConnectionId;
         if (!project.id || !connectionId) {
            setCatalogConnection(null);
            return;
         }

         const result = await catalogService.listConnections(project.id);
         if (cancelled) {
            return;
         }

         if (!result.succeed || !result.data) {
            setCatalogConnection(null);
            return;
         }

         const match = result.data.find(
            (connection) => connection.id === connectionId
         );
         setCatalogConnection(match || null);
      };

      void loadCatalogConnectionName();

      return () => {
         cancelled = true;
      };
   }, [catalogService, chatSession?.defaultCatalogConnectionId, project.id]);

   const catalogScopeLabel = [
      catalogConnection?.displayName,
      chatSession?.defaultNamespace,
      chatSession?.defaultEntityId
   ]
      .filter(Boolean)
      .join(" / ");
   const catalogButtonLabel =
      catalogScopeLabel || catalogConnection?.displayName || "Data source";
   const isExternalSourceUnavailable = Boolean(
      catalogConnection &&
      catalogConnection.connectionKind === "external" &&
      !catalogConnection.isQueryReady
   );
   const sourceUnavailableMessage =
      catalogConnection?.readinessReason === "queued"
         ? "This data source is queued for its initial sync."
         : catalogConnection?.readinessReason === "running"
           ? "This data source is syncing right now."
           : catalogConnection?.readinessReason === "failed"
             ? catalogConnection.lastSyncError ||
               "The latest data source sync failed."
             : "This data source is not ready for chat yet.";
   const resolveImageBlob = React.useCallback<MarkdownImageBlobResolver>(
      async ({ fileId }) => {
         const result = await fileService.downloadFile(fileId, project.id);
         return result.succeed ? (result.data?.blob ?? null) : null;
      },
      [fileService, project.id]
   );

   const isSessionSettingsReadOnly = !isOwner;

   return (
      <PageContainer
         key={`chat-session-${chatSessionId}`}
         title={displaySessionName}
         routeName={RouteNames.PROJECT}
         project={project}
         showBreadcrumb={false}
         showPageTitle={false}
         fluid={true}
         style={{ height: "100%" }}
      >
         <Layout
            style={{
               height: "100%",
               overflow: "hidden"
            }}
         >
            {/* Artifacts Sidebar - Only render when artifacts exist */}
            {artifacts.length > 0 && isSidebarOpen && (
               <Sider
                  width="60%"
                  style={{
                     backgroundColor: token.colorBgContainer,
                     borderRight: `1px solid ${token.colorBorder}`
                  }}
               >
                  <ProjectChatArtifactsPanel
                     artifacts={artifacts}
                     onRemoveArtifact={removeArtifact}
                     onAutoRename={(title) => updateChatSession(title)}
                  />
               </Sider>
            )}

            {/* Main Chat Area */}
            <Layout
               style={{
                  background: token.colorBgContainer
               }}
            >
               <Content
                  style={{
                     display: "flex",
                     flexDirection: "column",
                     height: "100%",
                     background: token.colorBgContainer,
                     position: "relative"
                  }}
               >
                  {isMessagesLoading && chatSessionId ? (
                     <Flex
                        align="center"
                        justify="center"
                        style={{ height: "100%" }}
                     >
                        <LoadingSpinner />
                     </Flex>
                  ) : (
                     <>
                        <ChatHeader
                           displaySessionName={displaySessionName}
                           chatSession={chatSession}
                           messagesCount={messages.length}
                           hasArtifacts={artifacts.length > 0}
                           isSidebarOpen={isSidebarOpen}
                           setSidebarOpen={setSidebarOpen}
                           onSaveSessionName={
                              isOwner
                                 ? async (name: string) => {
                                      if (name.trim() && chatSession) {
                                         await updateChatSession(name.trim());
                                      }
                                   }
                                 : undefined
                           }
                           onDeleteSession={
                              isOwner
                                 ? async (sessionId: string) => {
                                      try {
                                         const success =
                                            await deleteChatSession(sessionId);
                                         if (success) {
                                            message.success("Chat deleted");
                                            navigate(
                                               getProjectChatSessionsPath(
                                                  project
                                               )
                                            );
                                            return true;
                                         }
                                         message.error("Failed to delete chat");
                                         return false;
                                      } catch (err) {
                                         console.error(
                                            "Failed to delete chat",
                                            err
                                         );
                                         message.error("Failed to delete chat");
                                         return false;
                                      }
                                   }
                                 : undefined
                           }
                           onOpenSessions={() =>
                              navigate(getProjectChatSessionsPath(project))
                           }
                        />

                        {!isOwner && (
                           <Alert
                              title="This chat session belongs to another user and is read-only."
                              type="info"
                              banner
                              showIcon
                           />
                        )}

                        <ChatMessagesView
                           messages={messages}
                           onPromptClick={async (msg: string) => {
                              if (isAvailable && isOwner)
                                 await sendMessage(msg);
                           }}
                           isMessagesLoading={isMessagesLoading}
                           ownerId={chatSession?.ownerId}
                           resolveImageBlob={resolveImageBlob}
                        />

                        {/* Sticky Input Area */}
                        {isOwner && (
                           <div
                              style={{
                                 padding: "0 24px",
                                 background: token.colorBgContainer
                                 // borderTop: `1px solid ${token.colorBorderSecondary}`,
                                 // boxShadow: "0 -4px 12px -8px rgba(0, 0, 0, 0.15)"
                              }}
                           >
                              <div
                                 style={{ maxWidth: "800px", margin: "0 auto" }}
                              >
                                 {isExternalSourceUnavailable && (
                                    <Alert
                                       type="warning"
                                       showIcon
                                       message="Data source unavailable"
                                       description={sourceUnavailableMessage}
                                       style={{ marginBottom: 12 }}
                                    />
                                 )}
                                 {!isExternalSourceUnavailable && (
                                    <ProjectChatInputArea
                                       foundationModels={modelCatalog}
                                       sessionId={chatSession?.id}
                                       showWarning={true}
                                       onSubmitMessage={async (message) => {
                                          await sendMessage(message);
                                       }}
                                       sessionSettingsAccessory={({
                                          disabled,
                                          pythonExecutionApprovalMode,
                                          onPythonExecutionApprovalModeChange
                                       }) => (
                                          <ChatSessionComposerControls
                                             disabled={
                                                disabled ||
                                                isSessionSettingsReadOnly
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
                                          <Button
                                             size="small"
                                             type="text"
                                             disabled
                                             icon={<DatabaseOutlined />}
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
                                                {catalogButtonLabel}
                                             </span>
                                          </Button>
                                       }
                                    />
                                 )}
                              </div>
                           </div>
                        )}
                     </>
                  )}
               </Content>
            </Layout>
         </Layout>
      </PageContainer>
   );
};

const ChatSessionDetailPage = () => {
   const { currentProject } = useProject();

   if (!currentProject) return null;

   return <ChatSessionDetailPageInternal project={currentProject} />;
};

export default ChatSessionDetailPage;
