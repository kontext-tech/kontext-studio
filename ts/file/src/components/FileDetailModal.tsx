import type { ApiErrorResult } from "@kontext-tech/common/types";
import type { FileModel } from "@kontext-tech/schema";
import { Modal, Spin } from "antd";
import { useEffect, useState } from "react";
import { useFileService } from "../hooks/useFileService";
import FileDetailView from "./FileDetailView";

export interface FileDetailModalProps {
   visible: boolean;
   fileId: string | null;
   projectId: string | null;
   onClose: () => void;
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>;
}

const FileDetailModal = ({
   visible,
   fileId,
   projectId,
   onClose,
   errorHandler
}: FileDetailModalProps) => {
   const [file, setFile] = useState<FileModel | null>(null);
   const [isLoading, setIsLoading] = useState<boolean>(false);
   const [error, setError] = useState<string | null>(null);

   const fileService = useFileService(errorHandler);

   useEffect(() => {
      const fetchFile = async () => {
         if (!fileId || !projectId || !visible) {
            setFile(null);
            setError(null);
            return;
         }

         setIsLoading(true);
         setError(null);

         try {
            const result = await fileService.getFileById(fileId, projectId);

            if (result.succeed && result.data) {
               setFile(result.data);
            } else if (result.succeed && result.data === null) {
               setError("File not found");
            } else {
               setError(result.error?.messages?.[0] || "Failed to load file");
            }
         } catch (fetchError) {
            console.error("Error fetching file:", fetchError);
            setError("Failed to load file");
         } finally {
            setIsLoading(false);
         }
      };

      void fetchFile();
   }, [fileId, fileService, projectId, visible]);

   const handleClose = () => {
      setFile(null);
      setError(null);
      onClose();
   };

   return (
      <Modal
         title={file ? `File: ${file.name}` : "File Details"}
         open={visible}
         onCancel={handleClose}
         footer={null}
         width={800}
         styles={{
            body: { maxHeight: "75vh", overflowY: "auto" }
         }}
      >
         {isLoading && <Spin />}

         {error && !isLoading && (
            <div style={{ textAlign: "center", padding: "2rem" }}>
               <p>{error}</p>
            </div>
         )}

         {file && !isLoading && !error && <FileDetailView file={file} />}
      </Modal>
   );
};

export default FileDetailModal;
