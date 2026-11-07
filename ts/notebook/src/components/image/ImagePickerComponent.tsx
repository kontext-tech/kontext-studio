import { logger } from "@kontext-tech/common";
import { ImagesOutlined } from "@kontext-tech/icons";
import type { FileModel } from "@kontext-tech/schema";
import { Button, Image, Input, Typography } from "antd";
import React, { useCallback, useEffect, useState } from "react";
import ImageListModal from "./ImageListModal";
import type { ImagePickerConfig, ImagePickerData } from "./imagePickerConfig";

const { Text } = Typography;

interface ImagePickerComponentProps {
   data: ImagePickerData;
   config: ImagePickerConfig;
   onChange: (data: ImagePickerData) => void;
   readonly?: boolean;
}

/**
 * React component for image picker functionality
 * Handles image preview, caption input, and image selection modal
 */
export const ImagePickerComponent: React.FC<ImagePickerComponentProps> = ({
   data,
   config,
   onChange,
   readonly = false
}) => {
   const [imageUrl, setImageUrl] = useState<string | null>(null);
   const [loading, setLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [modalOpen, setModalOpen] = useState(false);

   // Load image when resourceId changes
   useEffect(() => {
      if (!data.resourceId || !config.onDownloadImageResource) {
         logger.debug(`[ImagePickerComponent] Skipping image load:`, {
            hasResourceId: !!data.resourceId,
            hasDownloadFunction: !!config.onDownloadImageResource
         });

         const timeoutId = window.setTimeout(() => {
            setImageUrl(null);
            setError(null);
            setLoading(false);
         }, 0);

         return () => window.clearTimeout(timeoutId);
      }

      logger.debug(
         `[ImagePickerComponent] Loading image for resource: ${data.resourceId}`
      );

      let cancelled = false;
      const timeoutId = window.setTimeout(() => {
         setLoading(true);
         setError(null);
      }, 0);

      config
         .onDownloadImageResource(data.resourceId)
         .then((blob) => {
            if (cancelled) return;

            if (blob) {
               const url = URL.createObjectURL(blob);
               logger.debug(
                  `[ImagePickerComponent] Successfully loaded image for resource: ${data.resourceId}`
               );
               setImageUrl(url);
               setError(null);
            } else {
               console.error(
                  `[ImagePickerComponent] Download returned null for resource: ${data.resourceId}`
               );
               setImageUrl(null);
               setError("Failed to load image");
            }
         })
         .catch((err) => {
            if (cancelled) return;
            console.error(
               `[ImagePickerComponent] Error loading image for resource: ${data.resourceId}`,
               err
            );
            setImageUrl(null);
            setError("Failed to load image");
         })
         .finally(() => {
            if (!cancelled) {
               setLoading(false);
            }
         });

      // Cleanup function to cancel request and revoke URL
      return () => {
         cancelled = true;
         window.clearTimeout(timeoutId);
         if (imageUrl) {
            URL.revokeObjectURL(imageUrl);
         }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [data.resourceId, config.onDownloadImageResource]);

   // Cleanup URL on unmount
   useEffect(() => {
      return () => {
         if (imageUrl) {
            URL.revokeObjectURL(imageUrl);
         }
      };
   }, [imageUrl]);

   const handleCaptionChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
         onChange({
            ...data,
            caption: e.target.value
         });
      },
      [data, onChange]
   );

   const handleImageSelect = useCallback(
      (resource: FileModel) => {
         onChange({
            ...data,
            resourceId: resource.id || ""
         });
         setModalOpen(false);
      },
      [data, onChange]
   );

   const openImagePicker = useCallback(() => {
      if (!readonly) {
         setModalOpen(true);
      }
   }, [readonly]);

   const closeModal = useCallback(() => {
      setModalOpen(false);
   }, []);

   // Render image preview or placeholder
   const renderImagePreview = () => {
      if (loading) {
         return (
            <div
               style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: 100,
                  background: "var(--editor-border-secondary)",
                  borderRadius: 6,
                  border: "1px dashed var(--editor-border)"
               }}
            >
               <Text type="secondary">Loading image...</Text>
            </div>
         );
      }

      if (error || (!imageUrl && data.resourceId)) {
         return (
            <div
               style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: 100,
                  background: "rgba(255, 77, 79, 0.1)",
                  borderRadius: 6,
                  border: "1px solid #ef4444",
                  color: "#ff7875"
               }}
            >
               <Text type="danger">{error || "Failed to load image"}</Text>
            </div>
         );
      }

      if (imageUrl) {
         return (
            <Image
               src={imageUrl}
               alt={data.caption || ""}
               style={{
                  width: "auto",
                  maxWidth: "100%",
                  height: "auto",
                  borderRadius: 6
               }}
               preview={{
                  mask: false
               }}
            />
         );
      }

      // No image selected placeholder
      return (
         <div
            style={{
               display: "flex",
               alignItems: "center",
               justifyContent: "center",
               minHeight: 80,
               background: "var(--editor-border-secondary)",
               borderRadius: 6,
               border: "1px dashed var(--editor-border)",
               cursor: readonly ? "default" : "pointer"
            }}
            onClick={openImagePicker}
         >
            <Text type="secondary">
               {readonly ? "No image selected" : "Click to select an image"}
            </Text>
         </div>
      );
   };

   return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
         {/* Image Preview */}
         {renderImagePreview()}

         {/* Caption display for readonly mode (preview) */}
         {readonly && data.caption && (
            <div
               style={{
                  fontSize: 14,
                  color: "var(--editor-text-secondary)",
                  fontStyle: "italic",
                  marginTop: 8
               }}
            >
               {data.caption}
            </div>
         )}

         {/* Caption Input - Only show in edit mode */}
         {!readonly && (
            <Input
               placeholder="Enter image caption (optional)"
               value={data.caption || ""}
               onChange={handleCaptionChange}
               disabled={readonly}
               style={{
                  background: "var(--editor-primary)",
                  borderColor: "var(--editor-border-secondary)",
                  color: "var(--editor-text)"
               }}
            />
         )}

         {/* Picker Button */}
         {!readonly && (
            <div>
               <Button
                  icon={<ImagesOutlined />}
                  onClick={openImagePicker}
                  shape="round"
               >
                  {data.resourceId ? "Change Image" : "Select Image"}
               </Button>
            </div>
         )}

         {/* Image Selection Modal */}
         {modalOpen && (
            <ImageListModal
               open={modalOpen}
               onClose={closeModal}
               onSelect={handleImageSelect}
               fetchImageResources={
                  config.onFetchImageResources ||
                  (async () => ({ items: [], totalCount: 0 }))
               }
               downloadImageResource={
                  config.onDownloadImageResource || (async () => null)
               }
            />
         )}
      </div>
   );
};
