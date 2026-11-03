import { formatFileSize } from "@kontext-labs/common";
import { UploadOutlined } from "@kontext-labs/icons";
import type { ApiErrorResult } from "@kontext-labs/common/types";
import type {
   CreateMultipleFilesResponse,
   ProjectConfiguration
} from "@kontext-labs/schema";
import { useIsLocalMode } from "@kontext-labs/site";
import { useUiApp } from "@kontext-labs/ui";
import {
   Checkbox,
   Flex,
   Form,
   Modal,
   Typography,
   Upload,
   type UploadFile,
   type UploadProps
} from "antd";
import { useState } from "react";
import { useFileWorkflow } from "../hooks";

export interface FileUploadModalProps {
   open?: boolean;
   visible?: boolean;
   configuration: ProjectConfiguration;
   projectId: string;
   prefix?: string;
   onClose: () => void;
   onBatchUpload?: (
      files: Array<{ name: string; file: File }>,
      allowOverwrite: boolean,
      prefix?: string
   ) => Promise<{
      success: boolean;
      response?: CreateMultipleFilesResponse;
      error?: ApiErrorResult;
   }>;
   isLocalMode?: boolean;
   onSuccess?: () => void;
   onMessage?: (
      type: "success" | "error" | "warning" | "info",
      content: string
   ) => void;
   onWarningDialog?: (title: string, content: React.ReactNode) => void;
}

export const FileUploadModal = ({
   open,
   visible,
   configuration,
   projectId,
   prefix,
   onClose,
   onBatchUpload,
   isLocalMode,
   onSuccess,
   onMessage,
   onWarningDialog
}: FileUploadModalProps) => {
   const { message, modal } = useUiApp();
   const detectedLocalMode = useIsLocalMode();
   const { createMultipleFiles } = useFileWorkflow({
      projectId,
      enableListManagement: false
   });
   const [isUploading, setIsUploading] = useState(false);
   const [form] = Form.useForm();
   const resolvedOpen = open || visible || false;
   const resolvedIsLocalMode = isLocalMode ?? detectedLocalMode;
   const notify =
      onMessage ||
      ((type: "success" | "error" | "warning" | "info", content: string) =>
         message[type](content));
   const showWarningDialog =
      onWarningDialog ||
      ((title: string, content: React.ReactNode) =>
         modal.warning({
            title,
            content,
            width: 520,
            centered: true,
            maskClosable: true
         }));

   const allowedFileExtensions = configuration.allowedFileTypes.map(
      (fileType) => fileType.fileExtension
   );

   const handleUpload = async () => {
      setIsUploading(true);
      try {
         const values = await form.validateFields();
         const files = values.files as UploadFile<unknown>[];
         const allowOverwrite = values.allowOverwrite || false;

         if (!files?.length) {
            return;
         }

         const fileRequests = files.map((file) => ({
            name: file.name,
            file: file.originFileObj as File
         }));

         const result = await (onBatchUpload
            ? onBatchUpload(fileRequests, allowOverwrite, prefix)
            : createMultipleFiles(fileRequests, allowOverwrite, prefix));

         if (result.success && result.response) {
            const { successCount, failureCount, errors } = result.response;

            if (failureCount > 0 && errors?.length) {
               const warningMessage = `${successCount} files uploaded successfully, ${failureCount} failed`;
               const warningContent = (
                  <div>
                     <Typography.Text strong>{warningMessage}</Typography.Text>
                     <Flex
                        vertical
                        gap={4}
                        style={{ marginTop: 8, marginBottom: 0 }}
                     >
                        {errors.map((error: string, index: number) => (
                           <Typography.Text key={index}>
                              {error}
                           </Typography.Text>
                        ))}
                     </Flex>
                  </div>
               );

               showWarningDialog("Some files failed to upload", warningContent);
               notify("warning", warningMessage);
               console.error("Upload errors:", errors);
            } else if (successCount > 0) {
               notify(
                  "success",
                  `${successCount} files uploaded successfully.`
               );
            }

            if (resolvedIsLocalMode && successCount > 0) {
               notify(
                  "info",
                  "Background processing started in local mode. Catalog and knowledge updates may take a moment to appear."
               );
            }

            form.resetFields();
            onSuccess?.();
            onClose();
         } else {
            // Typed API failures carry the server's reason (duplicate names,
            // validation problems); the global error handler already surfaced
            // auth/session problems, so show the message inline.
            notify(
               "error",
               result.error?.messages?.join(" ") || "Failed to upload files."
            );
         }
      } catch (error) {
         console.error("Error uploading files:", error);
         notify("error", "Failed to upload files.");
      } finally {
         setIsUploading(false);
      }
   };

   const beforeUpload = (file: UploadFile<unknown>) => {
      const fileExtension =
         file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || "";

      const matchingFileType = configuration.allowedFileTypes.find(
         (fileType) => fileType.fileExtension.toLowerCase() === fileExtension
      );

      if (!matchingFileType) {
         notify("error", `File type "${fileExtension}" is not allowed.`);
         return Upload.LIST_IGNORE;
      }

      const isValidMimeType =
         file.type && matchingFileType.allowedContentTypes.includes(file.type);
      const isValidExtension =
         matchingFileType.fileExtension.toLowerCase() === fileExtension;

      if (!isValidMimeType && !isValidExtension) {
         notify(
            "error",
            `File type "${file.type || "unknown"}" is not allowed for "${fileExtension}" files.`
         );
         return Upload.LIST_IGNORE;
      }

      if (file.size! > configuration.maxFileBytesSize) {
         notify(
            "error",
            `File size exceeds the limit of ${formatFileSize(configuration.maxFileBytesSize)}.`
         );
         return Upload.LIST_IGNORE;
      }

      return false;
   };

   const uploadProps: UploadProps = {
      beforeUpload,
      multiple: true,
      maxCount: 10,
      accept: allowedFileExtensions.join(",")
   };

   return (
      <Modal
         title="Upload Files"
         open={resolvedOpen}
         onCancel={onClose}
         onOk={handleUpload}
         confirmLoading={isUploading}
      >
         <Form
            form={form}
            labelCol={{ span: 4 }}
            wrapperCol={{ span: 18 }}
            layout="horizontal"
         >
            <Form.Item
               name="files"
               label="Files"
               rules={[{ required: true, message: "Please select files." }]}
               valuePropName="fileList"
               getValueFromEvent={(event) => {
                  if (Array.isArray(event)) {
                     return event;
                  }
                  return event?.fileList;
               }}
            >
               <Upload.Dragger {...uploadProps}>
                  <p className="ant-upload-drag-icon">
                     <UploadOutlined />
                  </p>
                  <p className="ant-upload-text">
                     Click or drag files to this area to upload
                  </p>
                  <p className="ant-upload-hint">
                     * Allowed file types: {allowedFileExtensions.join(", ")}
                     <br />* Max file size:{" "}
                     {formatFileSize(configuration.maxFileBytesSize)}
                  </p>
               </Upload.Dragger>
            </Form.Item>
            <Form.Item
               name="allowOverwrite"
               valuePropName="checked"
               wrapperCol={{ offset: 4, span: 18 }}
            >
               <Checkbox>
                  Allow overwriting existing files with the same name
               </Checkbox>
            </Form.Item>
         </Form>
      </Modal>
   );
};
