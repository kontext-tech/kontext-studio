import { useFileWorkflow } from "@kontext-tech/file";
import type { FileModel } from "@kontext-tech/schema";
import { useUiApp } from "@kontext-tech/ui";
import { Form, Input, Modal } from "antd";
import { useEffect, useState } from "react";
import {
   DEFAULT_NOTEBOOK_NAME_PREFIX,
   NOTEBOOK_FILE_EXTENSION,
   NOTEBOOK_MIME_TYPE
} from "../constants";

export interface CreateNotebookModalProps {
   open: boolean;
   projectId: string;
   defaultName?: string;
   onCancel: () => void;
   onCreated: (file: FileModel) => void;
}

export const CreateNotebookModal = ({
   open,
   projectId,
   defaultName,
   onCancel,
   onCreated
}: CreateNotebookModalProps) => {
   const [form] = Form.useForm<{ name: string }>();
   const [loading, setLoading] = useState(false);
   const { message } = useUiApp();
   const { createFile } = useFileWorkflow({ projectId });

   useEffect(() => {
      if (!open) {
         return;
      }

      form.setFieldsValue({
         name:
            defaultName ??
            `${DEFAULT_NOTEBOOK_NAME_PREFIX} ${new Date().getTime()}`
      });
   }, [defaultName, form, open]);

   const handleOk = async () => {
      try {
         const values = await form.validateFields();
         setLoading(true);

         const notebookBaseName = values.name;
         const notebookNameWithExtension = notebookBaseName.endsWith(
            NOTEBOOK_FILE_EXTENSION
         )
            ? notebookBaseName
            : `${notebookBaseName}${NOTEBOOK_FILE_EXTENSION}`;

         const notebookContent = JSON.stringify({
            id: crypto.randomUUID(),
            title: notebookBaseName,
            created: Date.now(),
            modified: Date.now(),
            blocks: []
         });

         const createResult = await createFile({
            projectId,
            name: notebookNameWithExtension,
            file: new File([notebookContent], notebookNameWithExtension, {
               type: NOTEBOOK_MIME_TYPE
            })
         });

         if (createResult.success && createResult.file) {
            message.success("Notebook created successfully!");
            onCreated(createResult.file);
            form.resetFields();
         } else {
            message.error(
               createResult.error?.messages?.join(" ") ||
                  "Failed to create notebook."
            );
         }
      } catch (error) {
         console.error("Error creating notebook:", error);
      } finally {
         setLoading(false);
      }
   };

   return (
      <Modal
         title="Create New Notebook"
         open={open}
         onOk={handleOk}
         onCancel={onCancel}
         confirmLoading={loading}
         destroyOnHidden
         okText="Create"
      >
         <Form form={form} layout="vertical" preserve={false}>
            <Form.Item
               name="name"
               label="Notebook Name"
               rules={[
                  { required: true, message: "Please input notebook name!" }
               ]}
            >
               <Input placeholder="Enter notebook name" autoFocus />
            </Form.Item>
         </Form>
      </Modal>
   );
};
