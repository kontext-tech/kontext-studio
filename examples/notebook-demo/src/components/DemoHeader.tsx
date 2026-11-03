import { logoDark, logoLight } from "@kontext-tech/common";
import { ThemeSelector, useTheme } from "@kontext-tech/theme";
import { Flex, Layout, Menu, theme, Typography } from "antd";
import React from "react";

const { Header } = Layout;
const { Title } = Typography;

interface DemoHeaderProps {
   currentPage: string;
   onPageChange: (page: string) => void;
}

const DemoHeader: React.FC<DemoHeaderProps> = ({
   currentPage,
   onPageChange
}) => {
   const { siteLogo, isDarkMode } = useTheme();
   const { useToken } = theme;
   const { token } = useToken();

   const menuItems = [
      {
         key: "notebook",
         label: "Notebook Demo"
      }
   ];

   const displayLogo = siteLogo.startsWith("/")
      ? isDarkMode
         ? logoDark
         : logoLight
      : siteLogo || (isDarkMode ? logoDark : logoLight);

   return (
      <Header
         style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorder}`,
            padding: "0 24px"
         }}
      >
         <Flex align="center" gap="middle">
            <img src={displayLogo} alt="Logo" style={{ height: 24 }} />
            <Title
               level={4}
               style={{
                  margin: 0,
                  paddingLeft: "12px",
                  color: token.colorText,
                  borderLeft: `2px solid ${token.colorBorder}`
               }}
            >
               Notebook Development
            </Title>
         </Flex>
         <Flex align="center" gap="middle">
            <Menu
               mode="horizontal"
               selectedKeys={[currentPage]}
               items={menuItems}
               onClick={({ key }) => onPageChange(key)}
               style={{
                  backgroundColor: "transparent",
                  border: "none",
                  color: token.colorText
               }}
               theme={token.colorBgElevated === "#ffffff" ? "light" : "dark"}
            />
            <ThemeSelector />
         </Flex>
      </Header>
   );
};

export default DemoHeader;
