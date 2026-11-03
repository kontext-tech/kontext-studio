import type { ApiErrorResult } from "@kontext-labs/common";
import type { UiFeedback } from "@kontext-labs/ui";
import { useUser, UserAvatar } from "@kontext-labs/identity";
import type {
   UpdateUserProfileRequest,
   UserWithRolesModel
} from "@kontext-labs/schema";
import { CloseOutlined, SaveOutlined } from "@kontext-labs/icons";
import { Button, Card, Flex, Form, Input, Select, Typography } from "antd";
import React, { useEffect, useState } from "react";
import { useService } from "@kontext-labs/app-runtime/hooks";
import { AccountService } from "../AccountService";

export interface ProfileLanguageOption {
   value: string;
   label: string;
}

export interface ProfileEditFormProps {
   user: UserWithRolesModel;
   languageOptions: ProfileLanguageOption[];
   languageOptionsLoading?: boolean;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   ui?: UiFeedback;
   onSave: (updatedUser: UserWithRolesModel) => void;
   onCancel: () => void;
}

interface ProfileFormValues {
   email: string;
   firstName: string;
   lastName: string;
   preferredLanguageCode: string;
}

const ProfileEditForm: React.FC<ProfileEditFormProps> = ({
   user,
   languageOptions,
   languageOptionsLoading = false,
   errorHandler,
   ui,
   onSave,
   onCancel
}) => {
   const [form] = Form.useForm<ProfileFormValues>();
   const [saving, setSaving] = useState(false);
   const { updateUser } = useUser();
   const accountService = useService(AccountService, errorHandler);

   useEffect(() => {
      form.setFieldsValue({
         email: user.email || "",
         firstName: user.firstName,
         lastName: user.lastName || "",
         preferredLanguageCode: user.preferredLanguageCode || ""
      });
   }, [user, form]);

   const handleSubmit = async (values: ProfileFormValues) => {
      setSaving(true);

      try {
         const profileRequest: UpdateUserProfileRequest = {
            firstName: values.firstName,
            lastName: values.lastName || undefined,
            preferredLanguageCode: values.preferredLanguageCode || undefined
         };

         const updatedUser =
            await accountService.updateUserProfile(profileRequest);
         if (updatedUser.succeed && updatedUser.data) {
            updateUser(updatedUser.data);
            ui?.success("Profile updated successfully");
            onSave(updatedUser.data);
            return;
         }

         ui?.error(
            updatedUser.error?.messages?.[0] ||
               updatedUser.error?.title ||
               "Failed to update profile"
         );
      } finally {
         setSaving(false);
      }
   };

   return (
      <Card
         title="Edit Profile"
         style={{ width: "100%" }}
         extra={
            <Flex gap="small">
               <Button
                  icon={<CloseOutlined />}
                  onClick={onCancel}
                  disabled={saving}
               >
                  Cancel
               </Button>
               <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={() => form.submit()}
                  loading={saving}
               >
                  Save
               </Button>
            </Flex>
         }
      >
         <Flex vertical align="center" gap="middle">
            <UserAvatar user={user} size={96} />

            <Typography.Title level={3} style={{ margin: "8px 0" }}>
               Edit Your Profile
            </Typography.Title>

            <Form
               form={form}
               layout="vertical"
               style={{ width: "100%" }}
               onFinish={handleSubmit}
            >
               <Form.Item label="Email" name="email">
                  <Input disabled />
               </Form.Item>

               <Form.Item
                  label="First Name"
                  name="firstName"
                  rules={[
                     {
                        required: true,
                        message: "Please enter your first name"
                     }
                  ]}
               >
                  <Input placeholder="First Name" />
               </Form.Item>

               <Form.Item label="Last Name" name="lastName">
                  <Input placeholder="Last Name" />
               </Form.Item>

               <Form.Item
                  label="Preferred Language"
                  name="preferredLanguageCode"
               >
                  <Select
                     placeholder="Select preferred language"
                     loading={languageOptionsLoading}
                     allowClear
                     options={languageOptions}
                  />
               </Form.Item>
            </Form>
         </Flex>
      </Card>
   );
};

export default ProfileEditForm;
