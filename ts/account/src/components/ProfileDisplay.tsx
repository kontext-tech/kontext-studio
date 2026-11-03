import {
   CheckCircleOutlined,
   CloseCircleOutlined,
   EditOutlined
} from "@kontext-tech/icons";
import { UserAvatar } from "@kontext-tech/identity";
import type { UserWithRolesModel } from "@kontext-tech/schema";
import {
   Button,
   Card,
   Descriptions,
   Flex,
   Grid,
   Space,
   theme,
   Tooltip,
   Typography
} from "antd";
import React from "react";
import RoleDisplay from "./RoleDisplay";

export interface ProfileDisplayProps {
   user: UserWithRolesModel;
   loading?: boolean;
   preferredLanguageLabel?: string;
   onEdit?: () => void;
}

const ProfileDisplay: React.FC<ProfileDisplayProps> = ({
   user,
   loading = false,
   preferredLanguageLabel = "Not set",
   onEdit
}) => {
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();
   const { token } = theme.useToken();

   return (
      <Card
         loading={loading}
         variant="outlined"
         style={{ width: "100%" }}
         actions={
            onEdit
               ? [
                    <Button
                       key="edit"
                       type="link"
                       onClick={onEdit}
                       icon={<EditOutlined />}
                    >
                       Edit Profile
                    </Button>
                 ]
               : undefined
         }
      >
         <Flex vertical align="center" gap="middle">
            <UserAvatar user={user} size={96} />

            <Typography.Title level={3} style={{ margin: "8px 0" }}>
               {user.firstName} {user.lastName || ""}
            </Typography.Title>

            <Descriptions
               layout={screens.sm ? "horizontal" : "vertical"}
               column={1}
               style={{ width: "100%" }}
               styles={{
                  label: {
                     width: screens.sm ? "180px" : "auto",
                     textAlign: screens.sm ? "right" : "left"
                  },
                  content: { textAlign: "left" }
               }}
            >
               <Descriptions.Item label="User ID">
                  <Typography.Text copyable>{user.id}</Typography.Text>
               </Descriptions.Item>
               <Descriptions.Item label="Email">
                  <Space>
                     {user.email}
                     <Tooltip
                        title={
                           user.emailConfirmed
                              ? "Email verified"
                              : "Email not verified"
                        }
                     >
                        {user.emailConfirmed ? (
                           <CheckCircleOutlined
                              style={{ color: token.colorSuccess }}
                           />
                        ) : (
                           <CloseCircleOutlined
                              style={{ color: token.colorError }}
                           />
                        )}
                     </Tooltip>
                  </Space>
               </Descriptions.Item>
               <Descriptions.Item label="Preferred Language">
                  {preferredLanguageLabel}
               </Descriptions.Item>
               <Descriptions.Item label="Account Status">
                  {user.isEnabled ? "Active" : "Inactive"}
                  {user.isLockedOut && " (Locked)"}
               </Descriptions.Item>
               <Descriptions.Item label="Roles">
                  <RoleDisplay roles={user.roles} showEmptyMessage={true} />
               </Descriptions.Item>
            </Descriptions>
         </Flex>
      </Card>
   );
};

export default ProfileDisplay;
