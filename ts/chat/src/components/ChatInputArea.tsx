import { Sender } from "@ant-design/x";
import type {
   ModelCatalogEntry,
   PythonExecutionApprovalMode,
   ProjectModel
} from "@kontext-tech/schema";
import { useUiApp } from "@kontext-tech/ui";
import { CodeOutlined, RobotOutlined } from "@kontext-tech/icons";
import { Button, Dropdown, Flex, theme, Typography } from "antd";
import React, { useCallback, useState } from "react";
import type { ChatNavigationAdapter } from "../types/chatHost";
import {
   loadRememberedPythonApprovalMode,
   persistRememberedPythonApprovalMode,
   usePythonExecutionApprovalModal
} from "../hooks/usePythonExecutionApprovalModal";
import { useChat } from "../useChat";
import { useChatSessionStore } from "../stores/chatSessionStore";

const { useToken } = theme;

export interface ChatInputAreaRenderContext {
   inputValue: string;
   hasInput: boolean;
   sessionId?: string | null;
   isBusy: boolean;
   setInputValue: React.Dispatch<React.SetStateAction<string>>;
}

export interface ChatInputAreaSessionSettingsRenderContext {
   pythonExecutionApprovalMode: PythonExecutionApprovalMode;
   onPythonExecutionApprovalModeChange: (
      mode: PythonExecutionApprovalMode
   ) => Promise<void>;
   disabled: boolean;
}

type ChatInputAreaSlot =
   React.ReactNode | ((context: ChatInputAreaRenderContext) => React.ReactNode);

type ChatInputAreaSessionSettingsSlot =
   | React.ReactNode
   | ((context: ChatInputAreaSessionSettingsRenderContext) => React.ReactNode);

export interface ChatInputAreaProps {
   project: ProjectModel;
   foundationModels?: ModelCatalogEntry[];
   sessionId?: string | null;
   modelSelectionId?: string | undefined;
   showWarning?: boolean;
   onSubmitMessage?: (
      message: string,
      context?: {
         pythonExecutionApprovalMode: PythonExecutionApprovalMode;
      }
   ) => Promise<void>;
   contextAccessory?: React.ReactNode;
   sessionSettingsAccessory?: ChatInputAreaSessionSettingsSlot;
   navigationAdapter?: ChatNavigationAdapter;
   onCreateSessionName?: (message: string) => string;
   errorMessageOnCreate?: string;
   preSessionLeadingAction?: React.ReactNode;
   stagedAttachmentTray?: ChatInputAreaSlot;
   statusBanner?: ChatInputAreaSlot;
   composerHeaderContent?: ChatInputAreaSlot;
   composerContent?: ChatInputAreaSlot;
   isBusy?: boolean;
   errorHandler?: Parameters<typeof useChat>[1] extends infer T
      ? T extends { errorHandler?: infer H }
         ? H
         : never
      : never;
}

export const ChatInputArea: React.FC<ChatInputAreaProps> = ({
   project,
   foundationModels = [],
   sessionId,
   modelSelectionId,
   showWarning = false,
   onSubmitMessage,
   contextAccessory,
   sessionSettingsAccessory,
   navigationAdapter,
   onCreateSessionName,
   errorMessageOnCreate = "Failed to create chat session",
   preSessionLeadingAction,
   stagedAttachmentTray,
   statusBanner,
   composerHeaderContent,
   composerContent,
   isBusy = false,
   errorHandler
}) => {
   const { token } = useToken();
   const { message } = useUiApp();
   const [inputValue, setInputValue] = useState("");
   const [pendingApprovalMode, setPendingApprovalMode] =
      useState<PythonExecutionApprovalMode>(() =>
         loadRememberedPythonApprovalMode()
      );
   const requestPythonExecutionApproval = usePythonExecutionApprovalModal();
   const {
      sendMessage,
      createChatSession,
      isLoading: isAiResponding,
      isMessagesLoading,
      isAvailable,
      error,
      navigateHistory,
      chatSession,
      setPythonExecutionApprovalMode,
      setModelSelectionId
   } = useChat(project, {
      sessionId: sessionId || undefined,
      modelSelectionId,
      pythonExecutionApprovalMode: sessionId ? undefined : pendingApprovalMode,
      requestPythonExecutionApproval,
      errorHandler
   });
   const storeModelSelectionId = useChatSessionStore(
      (state) => state.modelSelectionId
   );

   const handleApprovalModeChange = useCallback(
      async (mode: PythonExecutionApprovalMode) => {
         persistRememberedPythonApprovalMode(mode);
         setPendingApprovalMode(mode);

         if (!chatSession?.id) {
            return;
         }

         const success = await setPythonExecutionApprovalMode(mode);
         if (!success) {
            message.error("Failed to update Python approval mode");
         }
      },
      [
         chatSession?.id,
         message,
         setPendingApprovalMode,
         setPythonExecutionApprovalMode
      ]
   );

   const effectiveApprovalMode =
      chatSession?.pythonExecutionApprovalMode || pendingApprovalMode;

   const handleSendMessage = useCallback(async () => {
      if (!inputValue.trim()) {
         return;
      }

      const messageToSend = inputValue;
      setInputValue("");

      if (onSubmitMessage) {
         try {
            await onSubmitMessage(messageToSend, {
               pythonExecutionApprovalMode: effectiveApprovalMode
            });
         } catch (error) {
            setInputValue(messageToSend);
            console.error("Failed to submit message:", error);
         }
         return;
      }

      if (!chatSession?.id) {
         try {
            const defaultSessionName = onCreateSessionName
               ? onCreateSessionName(messageToSend)
               : `Chat - ${new Date().toLocaleString()}`;
            const newSession = await createChatSession(
               defaultSessionName,
               undefined,
               {
                  pythonExecutionApprovalMode: effectiveApprovalMode
               }
            );

            if (newSession?.id) {
               if (navigationAdapter) {
                  await navigationAdapter.onSessionCreated({
                     project,
                     sessionId: newSession.id,
                     initialMessage: messageToSend
                  });
                  return;
               }

               await sendMessage(messageToSend);
               return;
            }

            setInputValue(messageToSend);
            message.error(error || errorMessageOnCreate);
            return;
         } catch (error) {
            setInputValue(messageToSend);
            message.error(errorMessageOnCreate);
            console.error(error);
            return;
         }
      }

      if (!isAvailable) {
         setInputValue(messageToSend);
         return;
      }

      try {
         await sendMessage(messageToSend);
      } catch (error) {
         setInputValue(messageToSend);
         console.error("Failed to send message:", error);
      }
   }, [
      chatSession?.id,
      createChatSession,
      error,
      errorMessageOnCreate,
      inputValue,
      isAvailable,
      message,
      navigationAdapter,
      onCreateSessionName,
      onSubmitMessage,
      effectiveApprovalMode,
      project,
      sendMessage
   ]);

   const handleKeyDown = useCallback(
      (event: React.KeyboardEvent) => {
         if (event.key === "ArrowUp") {
            event.preventDefault();
            const historyMessage = navigateHistory("up");
            if (historyMessage !== null) {
               setInputValue(historyMessage);
            }
         } else if (event.key === "ArrowDown") {
            event.preventDefault();
            const historyMessage = navigateHistory("down");
            if (historyMessage !== null) {
               setInputValue(historyMessage);
            }
         }
      },
      [navigateHistory]
   );

   const modelMenuItems = foundationModels.map((foundationModel) => ({
      key: foundationModel.selectionId,
      label: (
         <Flex vertical>
            <Typography.Text strong>
               {foundationModel.displayName}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
               {foundationModel.connectionKind}
            </Typography.Text>
         </Flex>
      ),
      disabled: !!chatSession
   }));

   const selectedModelId =
      chatSession?.modelSelectionId ||
      storeModelSelectionId ||
      modelSelectionId ||
      undefined;
   const selectedModel = foundationModels.find(
      (item) => item.selectionId === selectedModelId
   );
   const hasAvailableModels = foundationModels.length > 0;
   const metadataButtonStyle = {
      color: token.colorTextSecondary,
      maxWidth: "200px",
      minWidth: 0,
      flexShrink: 1,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "flex-start",
      fontSize: token.fontSizeSM,
      height: 24,
      paddingInline: 4
   } as const;
   const metadataLabelStyle = {
      display: "block",
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
   } as const;
   const approvalModeLabel =
      effectiveApprovalMode === "auto_approve" ? "Auto execution" : "Ask first";
   const senderBusy = isAiResponding || isMessagesLoading || isBusy;
   const renderContext: ChatInputAreaRenderContext = {
      inputValue,
      hasInput: inputValue.trim().length > 0,
      sessionId,
      isBusy: senderBusy,
      setInputValue
   };
   const sessionSettingsRenderContext: ChatInputAreaSessionSettingsRenderContext =
      {
         pythonExecutionApprovalMode: effectiveApprovalMode,
         onPythonExecutionApprovalModeChange: handleApprovalModeChange,
         disabled: senderBusy || !isAvailable || !hasAvailableModels
      };
   const resolveSlot = (slot?: ChatInputAreaSlot) =>
      typeof slot === "function" ? slot(renderContext) : slot;
   const resolveSessionSettingsSlot = (
      slot?: ChatInputAreaSessionSettingsSlot
   ) =>
      typeof slot === "function" ? slot(sessionSettingsRenderContext) : slot;
   const resolvedStatusBanner = resolveSlot(statusBanner);
   const resolvedAttachmentTray = resolveSlot(stagedAttachmentTray);
   const resolvedComposerHeaderContent = resolveSlot(composerHeaderContent);
   const resolvedComposerContent = resolveSlot(composerContent);
   const resolvedSessionSettingsAccessory = resolveSessionSettingsSlot(
      sessionSettingsAccessory
   );

   return (
      <div style={{ padding: "16px 0", flexShrink: 0 }}>
         {resolvedStatusBanner && (
            <div style={{ maxWidth: "800px", margin: "0 auto 12px" }}>
               {resolvedStatusBanner}
            </div>
         )}
         {resolvedAttachmentTray && (
            <div style={{ maxWidth: "800px", margin: "0 auto 12px" }}>
               {resolvedAttachmentTray}
            </div>
         )}
         {resolvedComposerContent && (
            <div style={{ maxWidth: "800px", margin: "0 auto 12px" }}>
               {resolvedComposerContent}
            </div>
         )}
         <Sender
            placeholder={
               !hasAvailableModels
                  ? "Configure a model provider to start chatting."
                  : "Ask me anything about your project..."
            }
            value={inputValue}
            onChange={setInputValue}
            onSubmit={handleSendMessage}
            onKeyDown={handleKeyDown}
            loading={senderBusy}
            disabled={senderBusy || !isAvailable || !hasAvailableModels}
            header={
               resolvedComposerHeaderContent ? (
                  <Sender.Header
                     open={true}
                     closable={false}
                     styles={{
                        content: {
                           padding: "6px 12px"
                        }
                     }}
                  >
                     {resolvedComposerHeaderContent}
                  </Sender.Header>
               ) : (
                  false
               )
            }
            suffix={false}
            style={{
               maxWidth: "800px",
               margin: "0 auto",
               boxShadow: token.boxShadowTertiary,
               borderRadius: token.borderRadiusLG
            }}
            footer={(actionNode) => (
               <Flex
                  justify="space-between"
                  align="center"
                  style={{ minWidth: 0 }}
               >
                  <Flex gap="small" align="center" style={{ minWidth: 0 }}>
                     {preSessionLeadingAction}
                     {contextAccessory}
                     {foundationModels.length > 1 ? (
                        <Dropdown
                           menu={{
                              items: modelMenuItems,
                              selectedKeys: [selectedModelId || ""],
                              onClick: ({ key }) => {
                                 if (!chatSession) {
                                    setModelSelectionId(key as string);
                                 }
                              }
                           }}
                        >
                           <Button
                              size="small"
                              type="text"
                              style={metadataButtonStyle}
                              icon={
                                 <RobotOutlined style={{ flex: "0 0 auto" }} />
                              }
                           >
                              <span style={metadataLabelStyle}>
                                 {selectedModel?.displayName || "Model"}
                              </span>
                           </Button>
                        </Dropdown>
                     ) : (
                        <Button
                           size="small"
                           type="text"
                           disabled
                           style={metadataButtonStyle}
                           icon={<RobotOutlined style={{ flex: "0 0 auto" }} />}
                        >
                           <span style={metadataLabelStyle}>
                              {selectedModel?.displayName || "Model"}
                           </span>
                        </Button>
                     )}
                     {sessionSettingsAccessory ? (
                        resolvedSessionSettingsAccessory
                     ) : (
                        <Dropdown
                           menu={{
                              items: [
                                 {
                                    type: "group",
                                    label: "Code execution",
                                    children: [
                                       {
                                          key: "always_ask",
                                          label: "Ask first"
                                       },
                                       {
                                          key: "auto_approve",
                                          label: "Auto execution"
                                       }
                                    ]
                                 }
                              ],
                              selectedKeys: [effectiveApprovalMode],
                              onClick: ({ key }) =>
                                 void handleApprovalModeChange(
                                    key as PythonExecutionApprovalMode
                                 )
                           }}
                        >
                           <Button
                              size="small"
                              type="text"
                              style={metadataButtonStyle}
                              icon={
                                 <CodeOutlined style={{ flex: "0 0 auto" }} />
                              }
                           >
                              <span style={metadataLabelStyle}>
                                 {approvalModeLabel}
                              </span>
                           </Button>
                        </Dropdown>
                     )}
                  </Flex>
                  {actionNode}
               </Flex>
            )}
         />
         {!hasAvailableModels && (
            <Typography.Text
               type="secondary"
               style={{
                  fontSize: "12px",
                  display: "block",
                  textAlign: "center",
                  marginTop: "8px"
               }}
            >
               No AI model is available for this project yet. Add a model
               connection to start chatting.
            </Typography.Text>
         )}
         {showWarning && (
            <Typography.Text
               type="secondary"
               style={{
                  fontSize: "12px",
                  display: "block",
                  textAlign: "center",
                  marginTop: "8px"
               }}
            >
               Agent can make mistakes, so double-check it
            </Typography.Text>
         )}
      </div>
   );
};

export default ChatInputArea;
