import { ArrowLeftOutlined } from "@kontext-labs/icons";
import { MetaTags } from "@kontext-labs/site";
import { Button, Flex, Result } from "antd";
import React from "react";
import { Link } from "react-router-dom";

const NotFoundPage: React.FC = () => {
   return (
      <Flex vertical gap="small">
         <MetaTags
            title="Page Not Found"
            description="The page you requested does not exist or has moved."
            type="website"
            canonicalUrl={window.location.href}
         />
         <Result
            status="404"
            title="404"
            subTitle="The page you requested does not exist or has moved."
            extra={
               <Link to="/">
                  <Button
                     type="primary"
                     size="large"
                     shape="round"
                     icon={<ArrowLeftOutlined />}
                  >
                     Back to Home
                  </Button>
               </Link>
            }
         />
      </Flex>
   );
};

export default NotFoundPage;
