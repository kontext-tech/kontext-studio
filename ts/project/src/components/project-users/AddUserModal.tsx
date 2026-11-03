import { logger } from "@kontext-tech/common";
import { PROJECT_ROLE_FILTER_OPTIONS } from "@kontext-tech/auth";
import { Form, Input, Modal, Select } from "antd";
import type { FormInstance } from "antd/es/form";
import { useEffect } from "react";

export interface AddUserModalProps {
   isVisible: boolean;
   isSubmitting: boolean;
   form: FormInstance;
   onOk: (values: { userId: string; roles: string[] }) => void;
   onCancel: () => void;
}

const AddUserModal: React.FC<AddUserModalProps> = ({
   isVisible,
   isSubmitting,
   form,
   onOk,
   onCancel
}) => {
   useEffect(() => {
      if (isVisible) {
         form.resetFields();
      }
   }, [isVisible, form]);

   return (
      <Modal
         title="Add User to Project"
         open={isVisible}
         onCancel={onCancel}
         confirmLoading={isSubmitting}
         onOk={() => {
            form
               .validateFields()
               .then((values) => {
                  onOk(values);
               })
               .catch((info) => {
                  logger.debug("Validate Failed:", info);
               });
         }}
         okText="Add User"
         destroyOnHidden
      >
         <Form form={form} layout="vertical" name="addUserForm">
            <Form.Item
               name="userId"
               label="User ID"
               rules={[
                  {
                     required: true,
                     message: "Please input the user's ID"
                  }
               ]}
            >
               <Input placeholder="Enter ID of the user to add" />
            </Form.Item>
            <Form.Item
               name="roles"
               label="Project Roles"
               rules={[
                  {
                     required: true,
                     message: "Please select at least one role"
                  }
               ]}
            >
               <Select
                  mode="multiple"
                  allowClear
                  placeholder="Select roles"
                  options={PROJECT_ROLE_FILTER_OPTIONS}
               />
            </Form.Item>
         </Form>
      </Modal>
   );
};

export default AddUserModal;
