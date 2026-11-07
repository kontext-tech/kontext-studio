import ImageTool from "@editorjs/image";
import { BlockIcons } from "@kontext-tech/common";
import { extractResourceId } from "@kontext-tech/file";
import type { ImageBlock } from "@kontext-tech/schema";
import type { BlockPreviewProps } from "@notebook/types/notebook";
import React from "react";

export class CustomImage extends ImageTool {
   private downloadImageResource?: (
      resourceId: string,
      onProgress?: (progress: number) => void
   ) => Promise<Blob | null>;

   // eslint-disable-next-line @typescript-eslint/no-explicit-any
   constructor(config: any) {
      super(config);

      // Access the download function from config (try multiple paths for compatibility)
      this.downloadImageResource =
         config.onDownloadImageResource ||
         config.config?.onDownloadImageResource ||
         config.uploader?.onDownloadImageResource;
   }

   // Override the render method to handle private resource authentication
   render(): HTMLDivElement {
      const element = super.render() as HTMLDivElement;

      // Set up MutationObserver to watch for img elements and handle authentication
      if (this.downloadImageResource) {
         const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
               // Handle new elements being added
               mutation.addedNodes.forEach((node) => {
                  if (node.nodeType === Node.ELEMENT_NODE) {
                     const element = node as Element;
                     if (element.tagName === "IMG") {
                        this.handleImageAuthentication(
                           element as HTMLImageElement
                        );
                     }
                     // Also check child elements
                     element.querySelectorAll("img").forEach((img) => {
                        this.handleImageAuthentication(img);
                     });
                  }
               });

               // Handle attribute changes (like src attribute changes on existing img elements)
               if (
                  mutation.type === "attributes" &&
                  mutation.attributeName === "src"
               ) {
                  const target = mutation.target as Element;
                  if (target.tagName === "IMG") {
                     this.handleImageAuthentication(target as HTMLImageElement);
                  }
               }
            });
         });

         // Watch for both child elements and attribute changes
         observer.observe(element, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["src"]
         });

         // Check existing img elements immediately
         element.querySelectorAll("img").forEach((img) => {
            this.handleImageAuthentication(img);
         });

         // Store observer reference for cleanup
         // eslint-disable-next-line @typescript-eslint/no-explicit-any
         (this as any)._observer = observer;
      }

      return element;
   }

   private handleImageAuthentication(img: HTMLImageElement): void {
      if (!this.downloadImageResource) return;

      const imageUrl = img.src;

      // Skip if already a blob URL, empty, or data URL
      if (
         !imageUrl ||
         imageUrl.startsWith("blob:") ||
         imageUrl.startsWith("data:")
      ) {
         return;
      }

      // Check if this is a resource URL that needs authentication
      if (
         imageUrl.includes("/api/resource/") ||
         imageUrl.includes("localhost:8002/api/resource/")
      ) {
         // Extract resource ID using utility function
         const resourceId = extractResourceId.fromApiUrl(imageUrl);

         if (resourceId) {
            // Mark this image as being processed to avoid duplicate processing
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            if ((img as any)._processingAuth) return;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (img as any)._processingAuth = true;

            // Try to download the image and use blob URL
            this.downloadImageResource(resourceId)
               .then((blob) => {
                  if (blob) {
                     const blobUrl = URL.createObjectURL(blob);
                     img.src = blobUrl;

                     // Store blob URL for cleanup
                     // eslint-disable-next-line @typescript-eslint/no-explicit-any
                     (img as any)._blobUrl = blobUrl;

                     // Clean up blob URL when image is removed
                     img.addEventListener("load", () => {
                        // Image loaded successfully
                     });

                     img.addEventListener("error", () => {
                        // Revert to original URL on error
                        img.src = imageUrl;
                     });
                  }
               })
               .catch(() => {
                  // Keep the original URL as fallback
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  delete (img as any)._processingAuth;
               });
         }
      }
   }

   // Override the save method to ensure correct data is saved
   save(): ImageBlock["data"] {
      return super.save() as ImageBlock["data"];
   }

   // Override the destroy method to clean up blob URLs
   destroy(): void {
      // Clean up observer
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if ((this as any)._observer) {
         // eslint-disable-next-line @typescript-eslint/no-explicit-any
         (this as any)._observer.disconnect();
      }

      // Find all img elements and clean up their blob URLs
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const element = (this as any).holder;
      if (element) {
         element.querySelectorAll("img").forEach((img: HTMLImageElement) => {
            // Clean up blob URLs we created
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            if ((img as any)._blobUrl) {
               // eslint-disable-next-line @typescript-eslint/no-explicit-any
               URL.revokeObjectURL((img as any)._blobUrl);
            }
            // Also clean up any blob URLs in src attribute
            if (img.src.startsWith("blob:")) {
               URL.revokeObjectURL(img.src);
            }
         });
      }
   }

   static get toolbox() {
      return { title: "Image" as const, icon: BlockIcons.image };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as ImageBlock["data"];

      return React.createElement(
         "div",
         { className: `cdx-block ${className}` }, // Use EditorJS block class
         React.createElement("img", {
            src: blockData.file.url,
            alt: blockData.caption || "",
            style: {
               maxWidth: "100%",
               height: "auto",
               display: "block",
               margin: "0 auto",
               ...(blockData.withBorder && {
                  border: "1px solid var(--editor-border-secondary)"
               }),
               ...(blockData.withBackground && {
                  backgroundColor: "var(--editor-border-secondary)",
                  padding: "16px"
               }),
               ...(blockData.stretched && { width: "100%" })
            }
         }),
         blockData.caption &&
            React.createElement("div", {
               className: "image-tool__caption", // Use EditorJS image caption class
               style: {
                  textAlign: "center",
                  marginTop: "8px",
                  fontSize: "14px",
                  color: "var(--editor-text-secondary)",
                  fontStyle: "italic"
               },
               dangerouslySetInnerHTML: { __html: blockData.caption }
            })
      );
   }

   /**
    */
}
