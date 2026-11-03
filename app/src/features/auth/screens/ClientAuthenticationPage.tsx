import { useUiApp } from "@kontext-tech/ui";
import { useUser } from "@kontext-tech/identity";
import { Card, Result, Spin, Typography } from "antd";
import React, { useCallback, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const { Text } = Typography;

/**
 * Python Login Page
 *
 * This page handles authentication for Python applications/scripts.
 * When a Python script needs user authentication, it will redirect here
 * with a callback URL parameter. After successful authentication,
 * this page will redirect to the callback URL with the access tokens.
 */
const ClientAuthenticationPage: React.FC = () => {
   const navigate = useNavigate();
   const [searchParams] = useSearchParams();
   const { user, tokens } = useUser();
   const { message } = useUiApp();

   const callbackUrl = searchParams.get("callback");

   // Wrap in useCallback to stabilize function reference
   const handleSuccessfulAuth = useCallback(() => {
      if (!callbackUrl || !tokens) return;

      try {
         const url = new URL(callbackUrl);

         // Add tokens as query parameters
         url.searchParams.set("access_token", tokens.accessToken);

         if (tokens.refreshToken) {
            url.searchParams.set("refresh_token", tokens.refreshToken);
         }

         // Calculate expires_in from expiration date
         if (tokens.expiresIn) {
            url.searchParams.set("expires_in", tokens.expiresIn.toString());
         }

         // Redirect to callback URL with tokens
         window.location.href = url.toString();
      } catch (error) {
         console.error("Error redirecting to callback:", error);
         message.error("Failed to complete Python authentication");
      }
   }, [callbackUrl, tokens, message]);

   useEffect(() => {
      // If no callback URL is provided, redirect to main app
      if (!callbackUrl) {
         message.error("No callback URL provided for Python authentication");
         navigate("/login");
         return;
      }

      // Validate callback URL (basic security check)
      try {
         const url = new URL(callbackUrl);
         // Only allow localhost callbacks for security
         if (url.hostname !== "localhost" && url.hostname !== "127.0.0.1") {
            message.error(
               "Invalid callback URL - only localhost callbacks are allowed"
            );
            navigate("/login");
            return;
         }
      } catch {
         message.error("Invalid callback URL format");
         navigate("/login");
         return;
      }

      // If user is authenticated via cookies, we need to re-authenticate to get tokens
      if (user && !tokens) {
         const loginUrl = `/login?rurl=${encodeURIComponent(
            `/client-login?callback=${encodeURIComponent(callbackUrl)}`
         )}&token=true`;
         navigate(loginUrl);
         return;
      }

      // If user is already authenticated with tokens, redirect with tokens
      if (user && tokens) {
         handleSuccessfulAuth();
      } else {
         // Redirect to login with return URL for token-based auth
         const loginUrl = `/login?rurl=${encodeURIComponent(
            `/client-login?callback=${encodeURIComponent(callbackUrl)}`
         )}&token=true`;
         navigate(loginUrl);
      }
   }, [user, tokens, callbackUrl, navigate, message, handleSuccessfulAuth]);

   // Show loading state while processing
   return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
         <Card className="w-full max-w-md">
            <Result
               icon={<Spin size="large" />}
               title="Authenticating Python Application"
               subTitle={
                  <div className="text-center space-y-2">
                     <Text type="secondary">
                        Processing authentication for your Python script...
                     </Text>
                     <div className="text-xs text-gray-400 break-all">
                        Callback: {callbackUrl}
                     </div>
                  </div>
               }
            />
         </Card>
      </div>
   );
};

export default ClientAuthenticationPage;
