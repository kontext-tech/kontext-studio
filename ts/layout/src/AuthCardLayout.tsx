import { getAppUrl } from "@kontext-tech/common/utils";
import { useTheme } from "@kontext-tech/theme";
import { Card, Col, Flex, Grid, Layout, Row, Typography } from "antd";
import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

const { useBreakpoint } = Grid;
const { Link } = Typography;

export interface AuthCardLayoutProps {
   isFullWidth?: boolean;
   footer?: ReactNode;
   logoAlt: string;
   logoHref?: string;
   logoWrapper?: "anchor" | "link";
}

export const AuthCardLayout = ({
   isFullWidth = false,
   footer,
   logoAlt,
   logoHref = getAppUrl(),
   logoWrapper = "anchor"
}: AuthCardLayoutProps) => {
   const screens = useBreakpoint();
   const { siteLogo } = useTheme();

   const getPadding = () => {
      if (screens.xs) return "24px";
      if (screens.sm) return "32px";
      if (screens.md) return "40px";
      if (screens.lg) return "48px";
      return "60px";
   };

   const columnSpans = isFullWidth
      ? {
           xs: 22,
           sm: 20,
           md: 18,
           lg: 16,
           xl: 12,
           xxl: 10
        }
      : {
           xs: 20,
           sm: 16,
           md: 12,
           xl: 8
        };

   const logo = <img src={siteLogo} width={180} alt={logoAlt} />;

   return (
      <Layout style={{ height: "100%", minHeight: "100vh" }}>
         <Row justify="center" align="middle" style={{ height: "100%" }}>
            <Col {...columnSpans}>
               <Flex vertical gap="large">
                  <Flex vertical align="center" gap="large">
                     <div style={{ marginTop: "24px" }}>
                        {logoWrapper === "link" ? (
                           <Link
                              href={logoHref}
                              style={{ display: "flex", alignItems: "center" }}
                           >
                              {logo}
                           </Link>
                        ) : (
                           <a
                              href={logoHref}
                              style={{ display: "flex", alignItems: "center" }}
                           >
                              {logo}
                           </a>
                        )}
                     </div>
                     <Card style={{ width: "100%", padding: getPadding() }}>
                        <Outlet />
                     </Card>
                  </Flex>
                  {footer}
               </Flex>
            </Col>
         </Row>
      </Layout>
   );
};
