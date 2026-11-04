import { Space, Typography, theme } from "antd";
import React from "react";
import { getPlatformVersion } from "./platformInfo";

const { Text } = Typography;
const { useToken } = theme;

export interface SidebarFooterProps {
   collapsed?: boolean;
}

export const SidebarFooter: React.FC<SidebarFooterProps> = ({
   collapsed = false
}) => {
   const { token } = useToken();
   const version = getPlatformVersion();

   if (collapsed) {
      return null;
   }

   const textStyle = {
      fontSize: "10px",
      color: token.colorTextTertiary
   };

   return (
      <div
         style={{
            padding: "12px 16px 16px",
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            backgroundColor: token.colorBgContainer
         }}
      >
         <Space orientation="vertical" size={2} style={{ width: "100%" }}>
            <Text style={textStyle}>Powered by Kontext - {version}</Text>
         </Space>
      </div>
   );
};
