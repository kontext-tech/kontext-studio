import type { ApiErrorResult } from "@kontext-labs/common";
import { useUser } from "@kontext-labs/identity";
import type { UiFeedback } from "@kontext-labs/ui";
import type { UserWithRolesModel } from "@kontext-labs/schema";
import { Button, Card, Flex, Spin, Typography } from "antd";
import React, { useCallback, useEffect, useState } from "react";
import ProfileDisplay from "./ProfileDisplay";
import ProfileEditForm, { type ProfileLanguageOption } from "./ProfileEditForm";

export interface ProfileManagerProps {
   initialEditMode?: boolean;
   onProfileSaved?: (updatedUser: UserWithRolesModel) => void;
   onEditComplete?: () => void;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   ui?: UiFeedback;
   languageOptions: ProfileLanguageOption[];
   languageOptionsLoading?: boolean;
}

const ProfileManager: React.FC<ProfileManagerProps> = ({
   initialEditMode = false,
   onProfileSaved,
   onEditComplete,
   errorHandler,
   ui,
   languageOptions,
   languageOptionsLoading = false
}) => {
   const { user, isLoading, fetchUser } = useUser();
   const [isEditing, setIsEditing] = useState(initialEditMode);

   const loadProfile = useCallback(() => {
      return fetchUser(errorHandler);
   }, [errorHandler, fetchUser]);

   useEffect(() => {
      if (user) {
         return;
      }

      const timeoutId = window.setTimeout(() => {
         void loadProfile();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [loadProfile, user]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         setIsEditing(initialEditMode);
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [initialEditMode]);

   const preferredLanguageLabel = (() => {
      if (!user?.preferredLanguageCode) {
         return "Not set";
      }

      return (
         languageOptions.find(
            (option) => option.value === user.preferredLanguageCode
         )?.label || "Not set"
      );
   })();

   const handleEditStart = () => {
      setIsEditing(true);
   };

   const handleEditCancel = () => {
      setIsEditing(false);
      onEditComplete?.();
   };

   const handleProfileSave = (updatedUser: UserWithRolesModel) => {
      setIsEditing(false);
      onProfileSaved?.(updatedUser);
      onEditComplete?.();
   };

   if (isLoading && !user) {
      return (
         <Flex justify="center" align="center" style={{ width: "100%" }}>
            <Spin />
         </Flex>
      );
   }

   if (!user) {
      return (
         <Card style={{ width: "100%" }}>
            <Flex vertical gap="middle" align="center">
               <Typography.Title level={4} style={{ margin: 0 }}>
                  Unable to load your profile
               </Typography.Title>
               <Typography.Text type="secondary">
                  We couldn&apos;t load your account details right now.
               </Typography.Text>
               <Button type="primary" onClick={() => void loadProfile()}>
                  Try Again
               </Button>
            </Flex>
         </Card>
      );
   }

   if (isEditing) {
      return (
         <ProfileEditForm
            user={user}
            languageOptions={languageOptions}
            languageOptionsLoading={languageOptionsLoading}
            errorHandler={errorHandler}
            ui={ui}
            onSave={handleProfileSave}
            onCancel={handleEditCancel}
         />
      );
   }

   return (
      <ProfileDisplay
         user={user}
         loading={isLoading}
         preferredLanguageLabel={preferredLanguageLabel}
         onEdit={handleEditStart}
      />
   );
};

export default ProfileManager;
