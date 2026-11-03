import { Flex, Layout, Typography, theme } from "antd";
import React from "react";
import { PlatformLegalLinks } from "./PlatformLegalLinks";
import { getPlatformVersion } from "./PlatformLegalLinks";

const { Footer } = Layout;
const { Text } = Typography;
const { useToken } = theme;

export interface AppFooterProps {
   showDetails?: boolean;
}

const AppFooter: React.FC<AppFooterProps> = ({ showDetails = false }) => {
   const { token } = useToken();
   const version = getPlatformVersion();

   const linkStyle = {
      fontSize: "12px",
      color: token.colorTextSecondary
   };

   return showDetails ? (
      <Footer
         style={{
            textAlign: "center",
            padding: showDetails ? "16px" : "24px 0"
         }}
      >
         <Flex wrap justify="space-between" style={{ width: "100%" }}>
            <Text type="secondary" style={{ fontSize: "12px" }}>
               {version}
            </Text>

            <PlatformLegalLinks linkStyle={linkStyle} separator={null} />
         </Flex>
      </Footer>
   ) : null;
};

export default AppFooter;
