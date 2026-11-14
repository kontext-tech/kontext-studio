import {
   ChatUploadPreparationService,
   useChatSessionStoreApi
} from "@kontext-tech/chat";
import { formatFileSize } from "@kontext-tech/common";
import {
   FileFormatType,
   type ChatUploadPreparationFailure,
   type ChatUploadPreparationStatus,
   type ProjectModel
} from "@kontext-tech/schema";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";

import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { Flex, Typography } from "antd";
import { useUiApp } from "@kontext-tech/ui";
import { useNavigate } from "react-router-dom";

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

interface PreparationNotice {
   type: "error" | "warning" | "info";
   title: string;
   description?: string;
}

export interface StartPreparedChatSessionArgs {
   sessionName: string;
   message: string;
   effectiveModelSelectionId?: string;
   pythonExecutionApprovalMode?: "always_ask" | "auto_approve";
}

export interface ChatAttachmentDeps {
   createSessionFn: (
      sessionName: string,
      modelSelectionId?: string,
      options?: Record<string, unknown>
   ) => Promise<{ id: string } | undefined | null>;
   deleteChatSession: (sessionId: string) => Promise<unknown>;
   clearActiveSession: () => void;
}

const getChatUploadableFileTypes = (
   configuration: ProjectModel["configuration"]
) =>
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

/**
 * Stages chat data-file attachments and drives the upload-preparation
 * workflow (start -> overwrite confirmation -> poll -> seed context).
 */
export const useChatAttachmentPreparation = (project: ProjectModel) => {
   const apiErrorHandler = useApiErrorHandler();
   const { message: messageApi, modal } = useUiApp();
   const { getRoutePath } = useRoute();
   const navigate = useNavigate();
   const chatUploadPreparationService = useDataService(
      ChatUploadPreparationService,
      apiErrorHandler
   );
   const chatSessionStoreApi = useChatSessionStoreApi();

   const fileInputRef = useRef<HTMLInputElement | null>(null);
   const isMountedRef = useRef(true);
   const [stagedAttachments, setStagedAttachments] = useState<
      StagedChatAttachment[]
   >([]);
   const [isPreparingAttachments, setIsPreparingAttachments] = useState(false);
   const [preparationNotice, setPreparationNotice] =
      useState<PreparationNotice | null>(null);

   useEffect(() => {
      isMountedRef.current = true;
      return () => {
         isMountedRef.current = false;
      };
   }, []);

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
      setPreparationNotice(null);
   };

   const removeStagedAttachment = (attachmentId: string) => {
      setStagedAttachments((current) =>
         current.filter((attachment) => attachment.id !== attachmentId)
      );
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
      setPreparationNotice(null);

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

   /**
    * Runs the upload-preparation pipeline and creates the chat session for
    * the staged attachments. Resolves when the session page navigation has
    * been issued; rejects (and sets `preparationNotice`) on failure.
    */
   const startPreparedChatSession = async (
      deps: ChatAttachmentDeps,
      {
         sessionName,
         message,
         effectiveModelSelectionId,
         pythonExecutionApprovalMode
      }: StartPreparedChatSessionArgs
   ) => {
      let notice: PreparationNotice | null = null;

      setPreparationNotice(null);
      setIsPreparingAttachments(true);

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
            startData = await requestPreparation(true);
         }

         const finalStatus = await pollChatUploadPreparation(startData.runId);
         const effectiveConnectionId =
            finalStatus.internalCatalogConnectionId ||
            startData.internalCatalogConnectionId;

         if (!effectiveConnectionId) {
            throw new Error("We couldn't start chat with the attached files.");
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

         const newSession = await deps.createSessionFn(
            sessionName,
            effectiveModelSelectionId,
            {
               defaultCatalogConnectionId: effectiveConnectionId,
               ...(pythonExecutionApprovalMode
                  ? { pythonExecutionApprovalMode }
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
            await deps.deleteChatSession(newSession.id);
            deps.clearActiveSession();
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
         setPreparationNotice(null);
         navigate(path, {
            state: {
               initialMessage: message,
               uploadPreparationWarning
            }
         });
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
   };

   return {
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
   };
};
