import { formatFileSize } from "@kontext-labs/common";
import { CopyOutlined, LoadingOutlined } from "@kontext-labs/icons";
import type { FileModel } from "@kontext-labs/schema";
import {
   Button,
   Flex,
   Input,
   Modal,
   Progress,
   Spin,
   Tooltip,
   Typography,
   message
} from "antd";
import { useEffect, useState } from "react";
import { useFileOperations } from "../hooks/useFileOperations";

const { Text } = Typography;

export interface ImagePreviewModalProps {
   visible: boolean;
   resource: FileModel | null;
   projectId: string;
   onClose: () => void;
}

const ImagePreviewModal = ({
   visible,
   resource,
   projectId,
   onClose
}: ImagePreviewModalProps) => {
   const { getFileData, getFileUrl } = useFileOperations({
      projectId
   });

   const [imageLoading, setImageLoading] = useState(true);
   const [imageUrl, setImageUrl] = useState<string | null>(null);
   const [downloadProgress, setDownloadProgress] = useState<number | null>(
      null
   );

   useEffect(() => {
      let url: string | null = null;
      let isCancelled = false;

      const fetchImage = async () => {
         if (resource && visible) {
            setImageLoading(true);
            setDownloadProgress(0);

            const result = await getFileData(resource.id!, (progress: number) =>
               setDownloadProgress(progress)
            );

            if (isCancelled) return;

            if (result) {
               setImageUrl(result.url);
               setImageLoading(false);
               setDownloadProgress(null);
               url = result.url;
            } else {
               setImageUrl(null);
               setImageLoading(false);
               setDownloadProgress(null);
            }
         } else {
            setImageUrl(null);
         }
      };

      void fetchImage();

      return () => {
         isCancelled = true;
         if (url) {
            window.URL.revokeObjectURL(url);
         }
      };
   }, [getFileData, resource, visible]);

   const handleCopyImageUrl = () => {
      if (!resource?.id) return;

      const apiUrl = getFileUrl(resource.id);

      navigator.clipboard
         .writeText(apiUrl)
         .then(() => {
            message.success("URL copied to clipboard");
         })
         .catch((error) => {
            console.error("Failed to copy URL:", error);
            message.error("Failed to copy URL to clipboard");
         });
   };

   return (
      <Modal
         open={visible}
         title={resource?.name || "Image Preview"}
         footer={null}
         onCancel={onClose}
         width={800}
         centered
      >
         {resource && (
            <Flex vertical align="center">
               {imageLoading && (
                  <Flex vertical align="center" style={{ padding: "40px 0" }}>
                     <Spin indicator={<LoadingOutlined spin />} size="large" />
                     {downloadProgress !== null && (
                        <Progress
                           percent={Math.round(downloadProgress * 100)}
                           status={downloadProgress < 1 ? "active" : "success"}
                           style={{ minWidth: 200, marginTop: 16 }}
                        />
                     )}
                  </Flex>
               )}
               {imageUrl && !imageLoading && (
                  <img
                     src={imageUrl}
                     alt={resource.name}
                     style={{
                        maxWidth: "100%",
                        maxHeight: "70vh",
                        display: "inline-block"
                     }}
                  />
               )}
               <Flex
                  vertical
                  gap="small"
                  style={{ marginTop: 16, width: "100%" }}
               >
                  <Text type="secondary">
                     {resource.contentType} ·{" "}
                     {formatFileSize(resource.size || 0)}
                  </Text>
                  <Flex gap="small">
                     <Input
                        readOnly
                        value={resource.id ? getFileUrl(resource.id) : ""}
                        style={{ flex: 1 }}
                     />
                     <Tooltip title="Copy API URL for article content">
                        <Button
                           icon={<CopyOutlined />}
                           onClick={handleCopyImageUrl}
                           disabled={!resource.id}
                        >
                           Copy URL
                        </Button>
                     </Tooltip>
                  </Flex>
               </Flex>
            </Flex>
         )}
      </Modal>
   );
};

export default ImagePreviewModal;
