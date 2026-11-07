import { getUserDisplayName } from "../utils/userUtils";
import type {
   UserWithProjectRolesModel,
   UserWithRolesModel
} from "@kontext-tech/schema";
import { Avatar, Space, Tooltip, Typography } from "antd";
import React, { useMemo } from "react";

const COLOR_PALETTE = [
   "#f44336",
   "#e91e63",
   "#9c27b0",
   "#673ab7",
   "#3f51b5",
   "#2196f3",
   "#03a9f4",
   "#00bcd4",
   "#009688",
   "#4caf50",
   "#8bc34a",
   "#cddc39",
   "#ffeb3b",
   "#ffc107",
   "#ff9800",
   "#ff5722",
   "#795548",
   "#607d8b"
];

function getColorForName(name: string): string {
   if (!name) return COLOR_PALETTE[0];

   let hash = 0;
   for (let index = 0; index < name.length; index += 1) {
      hash = (Math.imul(31, hash) + name.charCodeAt(index)) | 0;
   }

   return COLOR_PALETTE[Math.abs(hash) % COLOR_PALETTE.length];
}

function getInitials(
   firstName?: string | null,
   lastName?: string | null
): string {
   const first = firstName?.trim()?.[0]?.toUpperCase() ?? "";
   const last = lastName?.trim()?.[0]?.toUpperCase() ?? "";
   return first + last || "?";
}

type UserType = UserWithRolesModel | UserWithProjectRolesModel;

export interface UserAvatarProps {
   user?: UserType;
   size?: number | "large" | "small" | "default";
   showName?: boolean;
   namePosition?: "right" | "bottom";
   showTooltip?: boolean;
   showLastName?: boolean;
}

const UserAvatar: React.FC<UserAvatarProps> = ({
   user,
   size = "default",
   showName = false,
   namePosition = "right",
   showTooltip = false,
   showLastName = true
}) => {
   const initials = useMemo(
      () => getInitials(user?.firstName, user?.lastName),
      [user?.firstName, user?.lastName]
   );

   const backgroundColor = useMemo(() => {
      const fullName =
         `${user?.firstName ?? ""} ${user?.lastName ?? ""}`.trim();
      return getColorForName(fullName);
   }, [user?.firstName, user?.lastName]);

   const { displayName, fullName } = useMemo(() => {
      if (!user) {
         return { displayName: "", fullName: "" };
      }

      const resolvedFullName = getUserDisplayName(user);
      return {
         displayName: showLastName
            ? resolvedFullName
            : user.firstName || "User",
         fullName: resolvedFullName
      };
   }, [showLastName, user]);

   const avatarElement = showTooltip ? (
      <Tooltip title={fullName}>
         <Avatar size={size} style={{ backgroundColor }}>
            {initials}
         </Avatar>
      </Tooltip>
   ) : (
      <Avatar size={size} style={{ backgroundColor }}>
         {initials}
      </Avatar>
   );

   if (!showName || !displayName) {
      return avatarElement;
   }

   return (
      <Space
         direction={namePosition === "bottom" ? "vertical" : "horizontal"}
         align="center"
         size="small"
      >
         {avatarElement}
         <Typography.Text>{displayName}</Typography.Text>
      </Space>
   );
};

export default UserAvatar;
