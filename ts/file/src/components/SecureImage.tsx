import { useDataService } from "@kontext-labs/app-runtime/hooks";
import { LoadingOutlined } from "@kontext-labs/icons";
import { Flex, Image, Progress, Spin, Typography } from "antd";
import React, { useEffect, useState } from "react";
import { FileService } from "../services";

const { Text } = Typography;

export interface SecureImageProps {
   fileId?: string;
   projectId?: string;
   src?: string;
   alt?: string;
   style?: React.CSSProperties;
   showLoading?: boolean;
   showError?: boolean;
   fallbackTitle?: string;
   downloadFn?: (
      fileId: string,
      onProgress?: (progress: number) => void
   ) => Promise<Blob | null>;
   onLoad?: (url: string) => void;
   onError?: (error: unknown) => void;
}

const SecureImage: React.FC<SecureImageProps> = ({
   fileId,
   projectId,
   src,
   alt,
   style,
   showLoading = true,
   showError = true,
   fallbackTitle,
   downloadFn,
   onLoad,
   onError
}) => {
   const fileService = useDataService(FileService);

   const [imageLoading, setImageLoading] = useState(false);
   const [imageUrl, setImageUrl] = useState<string | null>(null);
   const [downloadProgress, setDownloadProgress] = useState<number | null>(
      null
   );
   const [error, setError] = useState<string | null>(null);

   useEffect(() => {
      let objectUrl: string | null = null;
      let isCancelled = false;

      const resolveImage = async () => {
         setError(null);

         let effectiveFileId = fileId;
         let canUseSrcDirectly = false;

         if (src) {
            if (src.startsWith("data:") || src.startsWith("http")) {
               if (src.startsWith("data:")) {
                  canUseSrcDirectly = true;
               } else {
                  const fileIdMatch = src.match(
                     /\/file\/([a-f0-9-]{36})\/download/i
                  );
                  if (fileIdMatch) {
                     effectiveFileId = fileIdMatch[1];
                  } else {
                     canUseSrcDirectly = true;
                  }
               }
            }
         }

         if (canUseSrcDirectly && src) {
            setImageUrl(src);
            setImageLoading(false);
            onLoad?.(src);
            return;
         }

         if (effectiveFileId && (downloadFn || projectId)) {
            setImageLoading(true);
            setDownloadProgress(0);

            try {
               let blob: Blob | null = null;

               if (downloadFn) {
                  blob = await downloadFn(
                     effectiveFileId,
                     (progress: number) => {
                        if (!isCancelled) setDownloadProgress(progress);
                     }
                  );
               } else if (projectId) {
                  const result = await fileService.downloadFile(
                     effectiveFileId,
                     projectId,
                     (progress: number) => {
                        if (!isCancelled) setDownloadProgress(progress);
                     }
                  );

                  if (result.succeed && result.data) {
                     blob = result.data.blob;
                  } else {
                     throw new Error(
                        result.error?.messages?.[0] ||
                           "Failed to download image"
                     );
                  }
               }

               if (isCancelled) return;

               if (blob) {
                  const url = window.URL.createObjectURL(blob);
                  objectUrl = url;
                  setImageUrl(url);
                  onLoad?.(url);
               } else {
                  throw new Error("Failed to load image data");
               }
            } catch (err: unknown) {
               const errorMessage =
                  err instanceof Error ? err.message : String(err);
               console.error("SecureImage: Failed to fetch image:", err);
               setError(errorMessage || "Failed to load image");
               onError?.(err);
            } finally {
               if (!isCancelled) {
                  setImageLoading(false);
                  setDownloadProgress(null);
               }
            }
         } else {
            setImageLoading(false);
            if (!canUseSrcDirectly && !effectiveFileId) {
               setError("No image source provided");
            }
         }
      };

      resolveImage();

      return () => {
         isCancelled = true;
         if (objectUrl) {
            window.URL.revokeObjectURL(objectUrl);
         }
      };
   }, [fileId, projectId, src, fileService, downloadFn, onLoad, onError]);

   if (imageLoading && showLoading) {
      return (
         <Flex
            vertical
            align="center"
            justify="center"
            gap="middle"
            style={{ minHeight: 120, width: "100%", ...style }}
         >
            <Spin indicator={<LoadingOutlined spin />} />
            {downloadProgress !== null && downloadProgress > 0 && (
               <Progress
                  percent={Math.round(downloadProgress * 100)}
                  size="small"
                  style={{ maxWidth: 120 }}
               />
            )}
            <Text type="secondary" style={{ fontSize: 12 }}>
               Loading...
            </Text>
         </Flex>
      );
   }

   if (error && showError) {
      return (
         <Flex
            vertical
            align="center"
            justify="center"
            style={{
               padding: 16,
               border: "1px dashed #ffccc7",
               borderRadius: 8,
               backgroundColor: "#fff2f0",
               minHeight: 120,
               width: "100%",
               ...style
            }}
         >
            <Text type="danger">{fallbackTitle || "Failed to load image"}</Text>
            <Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>
               {error}
            </Text>
         </Flex>
      );
   }

   if (!imageUrl) {
      return null;
   }

   return (
      <Image
         src={imageUrl}
         alt={alt || fallbackTitle}
         style={{
            maxWidth: "100%",
            borderRadius: 8,
            ...style
         }}
      />
   );
};

export default SecureImage;
