import { navigateToUrl } from "@kontext-labs/common/utils";
import { createUrlWithReturnParam } from "../utils/navigationUtils";
import { Button } from "antd";
import type { ButtonProps } from "antd/es/button";
import React from "react";

export interface SignInButtonProps extends Omit<ButtonProps, "onClick"> {
   children?: React.ReactNode;
   loginHref?: string;
   loginPath?: string;
   includeReturnUrl?: boolean;
   returnUrl?: string;
   onBeforeNavigate?: () => Promise<void> | void;
   onNavigate?: (href: string) => void;
}

const SignInButton: React.FC<SignInButtonProps> = ({
   children = "Sign In",
   loginHref,
   loginPath,
   includeReturnUrl = false,
   returnUrl,
   onBeforeNavigate,
   onNavigate,
   type = "primary",
   ...buttonProps
}) => {
   const resolvedReturnUrl =
      returnUrl ?? `${window.location.pathname}${window.location.search}`;
   const resolvedLoginHref =
      loginHref ||
      (loginPath
         ? includeReturnUrl
            ? createUrlWithReturnParam(loginPath, resolvedReturnUrl)
            : loginPath
         : null);

   const handleSignIn = async () => {
      if (!resolvedLoginHref) {
         throw new Error(
            "SignInButton requires either `loginHref` or `loginPath`"
         );
      }

      await onBeforeNavigate?.();

      if (onNavigate) {
         onNavigate(resolvedLoginHref);
         return;
      }

      navigateToUrl(resolvedLoginHref);
   };

   return (
      <Button type={type} onClick={handleSignIn} {...buttonProps}>
         {children}
      </Button>
   );
};

export default SignInButton;
