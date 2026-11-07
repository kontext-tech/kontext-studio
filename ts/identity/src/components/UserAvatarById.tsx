import { UserOutlined } from "@kontext-tech/icons";
import { Avatar, Tooltip } from "antd";
import React, { useMemo } from "react";
import { IdentityService } from "../IdentityService";
import { useUserStore } from "../userStore";

export interface UserAvatarByIdProps {
   userId: string;
   size?: number | "large" | "small" | "default";
   showTooltip?: boolean;
   tooltipText?: string;
   version?: string;
}

const UserAvatarById: React.FC<UserAvatarByIdProps> = ({
   userId,
   size = "default",
   showTooltip = false,
   tooltipText = "User",
   version = "default"
}) => {
   const accessToken = useUserStore((state) => state.tokens?.accessToken);

   const avatarUrl = useMemo(() => {
      const identityService = new IdentityService({ accessToken });
      return identityService.getUserAvatarUrl(userId, version);
   }, [accessToken, userId, version]);

   const avatarElement = (
      <Avatar
         size={size}
         src={avatarUrl}
         icon={<UserOutlined />}
         alt={`Avatar for ${tooltipText}`}
      />
   );

   if (showTooltip) {
      return <Tooltip title={tooltipText}>{avatarElement}</Tooltip>;
   }

   return avatarElement;
};

export default UserAvatarById;
