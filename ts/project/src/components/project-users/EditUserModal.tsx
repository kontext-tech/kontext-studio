import { logger } from "@kontext-labs/common";
import { PROJECT_ROLE_FILTER_OPTIONS } from "@kontext-labs/auth";
import { getUserDisplayName } from "@kontext-labs/identity";
import type { UserWithProjectRolesModel } from "@kontext-labs/schema";
import { Form, Modal, Select, Typography } from "antd";
import type { FormInstance } from "antd/es/form";
import { useEffect } from "react";

const { Text } = Typography;

export interface EditUserModalProps {
   isVisible: boolean;
   isSubmitting: boolean;
   form: FormInstance;
   editingUser: UserWithProjectRolesModel | null;
   onOk: (values: { roles: string[] }) => void;
   onCancel: () => void;
}

const EditUserModal: React.FC<EditUserModalProps> = ({
   isVisible,
   isSubmitting,
   form,
   editingUser,
   onOk,
   onCancel
}) => {
   useEffect(() => {
      if (isVisible && editingUser) {
         form.resetFields();
         form.setFieldsValue({
            roles: editingUser.projectRoles || []
         });
      }
   }, [isVisible, editingUser, form]);

   const displayName = editingUser ? getUserDisplayName(editingUser) : "User";

   return (
      <Modal
         title={`Edit Roles for ${displayName}`}
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
         okText="Save Changes"
         destroyOnHidden
      >
         <Form form={form} layout="vertical" name="editUserRolesForm">
            <Form.Item label="User">
               <Text>
                  {displayName} (ID: {editingUser?.id})
               </Text>
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

export default EditUserModal;
