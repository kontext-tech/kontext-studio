import { Flex, Layout, Typography, theme } from "antd";
import React from "react";
import { getPlatformVersion } from "./platformInfo";

const { Footer } = Layout;
const { Link, Text } = Typography;
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

            <Flex gap="small" align="center">
               <Link
                  href="https://github.com/kontext-tech/kontext-studio/blob/main/LICENSE"
                  target="_blank"
                  style={linkStyle}
               >
                  License
               </Link>
               <Text type="secondary" style={linkStyle}>
                  ·
               </Text>
               <Link
                  href="https://github.com/kontext-tech/kontext-studio/blob/main/THIRD_PARTY_NOTICES.md"
                  target="_blank"
                  style={linkStyle}
               >
                  Third-party notices
               </Link>
            </Flex>
         </Flex>
      </Footer>
   ) : null;
};

export default AppFooter;
