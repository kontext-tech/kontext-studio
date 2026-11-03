import { AgentIcon, RobotOutlined } from "@kontext-labs/icons";
import { Avatar, theme } from "antd";

export interface RobotAvatarProps {
   size?: number | "large" | "small" | "default";
   className?: string;
   style?: React.CSSProperties;
   icon?: string;
}

const RobotAvatar = ({
   size = "default",
   className,
   style,
   icon: iconName
}: RobotAvatarProps) => {
   const { token } = theme.useToken();

   const icon = iconName ? <AgentIcon icon={iconName} /> : <RobotOutlined />;

   return (
      <Avatar
         size={size}
         style={{
            backgroundColor: token.colorPrimary,
            ...style
         }}
         className={className}
         icon={icon}
      />
   );
};

export default RobotAvatar;
