import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { LocalSetupService } from "@/services/LocalSetupService";
import { K_RETURN_URL } from "@kontext-labs/auth";
import { navigateToUrl } from "@kontext-labs/common/utils";
import { MetaTags } from "@kontext-labs/site";
import { useIsLocalMode, useSiteConfigStore } from "@kontext-labs/site";
import { useUiApp } from "@kontext-labs/ui";
import { useUserStore } from "@kontext-labs/identity";
import { Button, Checkbox, Flex, Form, Input, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const { Paragraph } = Typography;

const TERMS_VERSION = "1.0";
const TERMS_URL =
   "https://github.com/kontext-tech/kontext-studio/blob/main/TERMS.md";
const PRIVACY_URL =
   "https://github.com/kontext-tech/kontext-studio/blob/main/PRIVACY.md";

const LocalSetupPage = () => {
   const [loading, setLoading] = useState(false);
   const localMode = useIsLocalMode();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const navigate = useNavigate();
   const [searchParams] = useSearchParams();
   const { message, modal } = useUiApp();
   const apiErrorHandler = useApiErrorHandler();
   const { getGeneralRoutePath } = useRoute();
   const setTokens = useUserStore((state) => state.setTokens);
   const fetchUser = useUserStore((state) => state.fetchUser);
   const service = useMemo(() => new LocalSetupService(), []);

   useEffect(() => {
      if (!siteConfig) {
         return;
      }

      if (!localMode) {
         navigate(getGeneralRoutePath(RouteNames.LOGIN), { replace: true });
         return;
      }

      let cancelled = false;

      const checkStatus = async () => {
         const status = await service.getStatus();
         if (status.isSetupComplete && !cancelled) {
            navigate(
               {
                  pathname: getGeneralRoutePath(RouteNames.LOGIN),
                  search: searchParams.toString()
                     ? `?${searchParams.toString()}`
                     : ""
               },
               { replace: true }
            );
         }
      };

      void checkStatus();

      return () => {
         cancelled = true;
      };
   }, [
      getGeneralRoutePath,
      localMode,
      navigate,
      searchParams,
      service,
      siteConfig
   ]);

   const onFinish = async (values: {
      firstName: string;
      lastName?: string;
      email: string;
      acceptTerms: boolean;
   }) => {
      setLoading(true);
      try {
         const setupValues = {
            firstName: values.firstName,
            lastName: values.lastName,
            email: values.email
         };
         const tokens = await service.completeSetup(setupValues);
         setTokens(tokens);
         const loadedUser = await fetchUser(apiErrorHandler);
         if (!loadedUser) {
            throw new Error(
               "Local setup completed, but the user profile could not be loaded."
            );
         }
         window.localStorage.setItem(
            "kontext.terms.accepted",
            JSON.stringify({
               version: TERMS_VERSION,
               acceptedAt: new Date().toISOString()
            })
         );
         message.success("Local setup complete");
         const returnUrl = searchParams.get(K_RETURN_URL);
         if (returnUrl) {
            navigateToUrl(decodeURIComponent(returnUrl));
            return;
         }
         navigate(getGeneralRoutePath(RouteNames.HOME), { replace: true });
      } catch (error) {
         const content =
            error instanceof Error
               ? error.message
               : "Failed to complete local setup.";
         modal.error({
            title: "Setup failed",
            content
         });
      } finally {
         setLoading(false);
      }
   };

   return (
      <Flex vertical gap="middle">
         <MetaTags
            title="Local Setup"
            description="Create your local Kontext Studio profile"
            type="website"
            canonicalUrl={window.location.href}
         />
         <h1>Set up Kontext Studio</h1>
         <Paragraph type="secondary">
            Kontext Studio uses a local profile instead of an email/password
            sign-in flow. Create it once and the app will reuse it on subsequent
            launches.
         </Paragraph>
         <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
            <Form.Item
               label="First name"
               name="firstName"
               rules={[{ required: true, message: "First name is required." }]}
            >
               <Input autoComplete="given-name" />
            </Form.Item>
            <Form.Item label="Last name" name="lastName">
               <Input autoComplete="family-name" />
            </Form.Item>
            <Form.Item
               label="Email"
               name="email"
               rules={[
                  { required: true, message: "Email is required." },
                  { type: "email", message: "Enter a valid email address." }
               ]}
            >
               <Input autoComplete="email" />
            </Form.Item>
            <Form.Item
               name="acceptTerms"
               valuePropName="checked"
               rules={[
                  {
                     validator: (_, value) =>
                        value
                           ? Promise.resolve()
                           : Promise.reject(
                                new Error("Accept the terms to continue.")
                             )
                  }
               ]}
            >
               <Checkbox>
                  I agree to the{" "}
                  <a
                     href={TERMS_URL}
                     target="_blank"
                     rel="noreferrer"
                     onClick={(event) => event.stopPropagation()}
                  >
                     Terms of Use
                  </a>{" "}
                  and acknowledge the{" "}
                  <a
                     href={PRIVACY_URL}
                     target="_blank"
                     rel="noreferrer"
                     onClick={(event) => event.stopPropagation()}
                  >
                     Privacy Notice
                  </a>
                  .
               </Checkbox>
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
               <Button type="primary" htmlType="submit" loading={loading} block>
                  Create local profile
               </Button>
            </Form.Item>
         </Form>
      </Flex>
   );
};

export default LocalSetupPage;
