import { Flex, Result } from "antd";
import React from "react";
import SignInButton from "./SignInButton";

export interface AccessDeniedAlertProps {
   title?: string;
   description?: string;
   status?:
      "success" | "error" | "info" | "warning" | "401" | "404" | "403" | "500";
   minHeight?: string | number;
   loginHref?: string;
   signInAction?: React.ReactNode;
}

const AccessDeniedAlert: React.FC<AccessDeniedAlertProps> = ({
   title = "Access Denied",
   description = "You do not have permission to access this resource.",
   status = "403",
   minHeight,
   loginHref,
   signInAction
}) => {
   return (
      <Flex
         vertical
         align="center"
         justify="center"
         style={{ padding: "24px", minHeight: minHeight || "auto" }}
      >
         <Result
            status={status === "401" ? "warning" : status}
            title={status === "401" ? "Sign In Required" : title}
            subTitle={
               status === "401"
                  ? "Please sign in to access this resource."
                  : description
            }
            extra={
               status === "401"
                  ? signInAction ||
                    (loginHref ? <SignInButton loginHref={loginHref} /> : null)
                  : undefined
            }
            style={{ width: "100%" }}
         />
      </Flex>
   );
};

export default AccessDeniedAlert;
