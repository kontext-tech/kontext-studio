import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import {
   ChatInputArea as SharedChatInputArea,
   type ChatInputAreaProps as SharedChatInputAreaProps
} from "@kontext-tech/chat";
import { useProject } from "@kontext-tech/project";
import type { ModelCatalogEntry } from "@kontext-tech/schema";
import React from "react";
import { useNavigate } from "react-router-dom";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";

interface ChatInputAreaProps {
   foundationModels?: ModelCatalogEntry[];
   sessionId?: string | null;
   modelSelectionId?: string | undefined;
   showWarning?: boolean;
   onSubmitMessage?: SharedChatInputAreaProps["onSubmitMessage"];
   contextAccessory?: React.ReactNode;
   sessionSettingsAccessory?: SharedChatInputAreaProps["sessionSettingsAccessory"];
   preSessionLeadingAction?: SharedChatInputAreaProps["preSessionLeadingAction"];
   stagedAttachmentTray?: SharedChatInputAreaProps["stagedAttachmentTray"];
   statusBanner?: SharedChatInputAreaProps["statusBanner"];
   composerHeaderContent?: SharedChatInputAreaProps["composerHeaderContent"];
   composerContent?: SharedChatInputAreaProps["composerContent"];
   isBusy?: boolean;
}

const ProjectChatInputArea: React.FC<ChatInputAreaProps> = ({
   foundationModels = [],
   sessionId,
   modelSelectionId,
   showWarning = false,
   onSubmitMessage,
   contextAccessory,
   sessionSettingsAccessory,
   preSessionLeadingAction,
   stagedAttachmentTray,
   statusBanner,
   composerHeaderContent,
   composerContent,
   isBusy
}) => {
   const { currentProject } = useProject();
   const apiErrorHandler = useApiErrorHandler();
   const navigate = useNavigate();
   const { getRoutePath } = useRoute();

   if (!currentProject) {
      return null;
   }

   const sharedProps: SharedChatInputAreaProps = {
      project: currentProject,
      foundationModels,
      sessionId,
      modelSelectionId,
      showWarning,
      onSubmitMessage,
      contextAccessory,
      sessionSettingsAccessory,
      preSessionLeadingAction,
      stagedAttachmentTray,
      statusBanner,
      composerHeaderContent,
      composerContent,
      isBusy,
      errorHandler: apiErrorHandler,
      navigationAdapter: {
         onSessionCreated: async ({
            project,
            sessionId: createdSessionId,
            initialMessage
         }) => {
            const path = getRoutePath(
               RouteNames.PROJECT_CHAT_SESSION_DETAIL,
               project,
               { sessionId: createdSessionId }
            );
            navigate(path, { state: { initialMessage } });
         }
      }
   };

   return <SharedChatInputArea {...sharedProps} />;
};

export default ProjectChatInputArea;
