import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { AuthService, K_RETURN_URL } from "@kontext-tech/auth";
import { navigateToUrl } from "@kontext-tech/common/utils";
import { MetaTags } from "@kontext-tech/site";
import { useIsLocalMode, useSiteConfigStore } from "@kontext-tech/site";
import { useUser, useUserStore } from "@kontext-tech/identity";
import { Alert, Button, Flex, Spin } from "antd";
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const LoginPage: React.FC = () => {
   const [loading, setLoading] = useState(true);
   const [statusMessage, setStatusMessage] = useState<string | null>(null);
   const localMode = useIsLocalMode();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);

   const navigate = useNavigate();
   const { isAuthenticated, tokens } = useUser();
   const setTokens = useUserStore((state) => state.setTokens);
   const fetchUser = useUserStore((state) => state.fetchUser);
   const [searchParams] = useSearchParams();
   const { getGeneralRoutePath } = useRoute();
   const authService = useMemo(() => new AuthService({}), []);
   const wasRedirected = searchParams.has(K_RETURN_URL);

   useEffect(() => {
      if (isAuthenticated && tokens) {
         const returnUrl = searchParams.get(K_RETURN_URL);
         if (returnUrl) {
            navigateToUrl(decodeURIComponent(returnUrl));
            return;
         }
         navigate(getGeneralRoutePath(RouteNames.HOME), { replace: true });
         return;
      }

      if (!siteConfig) {
         return;
      }

      let cancelled = false;

      const bootstrap = async () => {
         try {
            if (localMode) {
               const tokenResult = await authService.bootstrap();
               if (!tokenResult.succeed) {
                  throw new Error(
                     tokenResult.error?.messages.join(" ") ||
                        "Failed to load local authentication state."
                  );
               }

               if (tokenResult.data) {
                  setTokens(tokenResult.data);
                  const loadedUser = await fetchUser();
                  if (!loadedUser) {
                     throw new Error(
                        "Local identity bootstrap did not return a user."
                     );
                  }
                  return;
               }

               const setupSearchParams = new URLSearchParams();
               const returnUrl = searchParams.get(K_RETURN_URL);
               if (returnUrl) {
                  setupSearchParams.set(K_RETURN_URL, returnUrl);
               }

               const setupPath = getGeneralRoutePath(RouteNames.LOCAL_SETUP);
               const queryString = setupSearchParams.toString();
               navigate(
                  queryString ? `${setupPath}?${queryString}` : setupPath,
                  { replace: true }
               );
               return;
            }

            const bootstrapResult = await authService.getHostBootstrap();
            if (!bootstrapResult.succeed) {
               throw new Error(
                  bootstrapResult.error?.messages.join(" ") ||
                     "Failed to load host authentication state."
               );
            }

            const platformLoginUrl =
               bootstrapResult.data?.loginUrl ??
               getGeneralRoutePath(RouteNames.HOME);
            window.location.assign(platformLoginUrl);
         } catch (error) {
            if (!cancelled) {
               setStatusMessage(
                  error instanceof Error
                     ? error.message
                     : "Unable to continue to sign-in."
               );
            }
         } finally {
            if (!cancelled) {
               setLoading(false);
            }
         }
      };

      void bootstrap();

      return () => {
         cancelled = true;
      };
   }, [
      authService,
      fetchUser,
      getGeneralRoutePath,
      isAuthenticated,
      localMode,
      navigate,
      searchParams,
      setTokens,
      siteConfig,
      tokens
   ]);

   return (
      <Flex vertical gap="small">
         <MetaTags
            title="Sign In"
            description="Sign in to your Kontext account"
            type="website"
            canonicalUrl={window.location.href}
         />

         <h1>{localMode ? "Starting local Kontext" : "Continue to Kontext"}</h1>
         {wasRedirected && (
            <Alert
               description="Please sign in to access the requested page."
               type="info"
               showIcon
               banner
               style={{ marginBottom: 16 }}
            />
         )}
         <Alert
            type={statusMessage ? "error" : "info"}
            showIcon
            message={
               statusMessage
                  ? "Unable to continue"
                  : localMode
                    ? "Preparing local developer access"
                    : "Redirecting to Kontext sign-in"
            }
            description={
               statusMessage ??
               (localMode
                  ? "Kontext will fetch a long-lived local developer JWT directly from the host bootstrap API."
                  : "Authentication is now handled by Kontext.")
            }
         />
         <Flex justify="center" style={{ padding: "16px 0" }}>
            {loading ? (
               <Spin size="large" />
            ) : (
               <Button type="primary" onClick={() => window.location.reload()}>
                  Try again
               </Button>
            )}
         </Flex>
      </Flex>
   );
};

export default LoginPage;
