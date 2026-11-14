import { usePythonEnvironment } from "@/hooks/usePythonEnvironment";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { CodeOutlined } from "@kontext-tech/icons";
import { useUiFeedback } from "@kontext-tech/ui";
import { SiteFeature } from "@kontext-tech/schema";
import { useSiteConfigStore } from "@kontext-tech/site";
import { Alert, Button, Space } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const DISMISSED_KEY = "kontext.python-env-banner.dismissed";

const PythonEnvironmentBanner = () => {
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const enabled =
      siteConfig?.features?.includes(SiteFeature.PYTHON_ENVIRONMENT) ?? false;
   const { environment, isLoading, isPreparing, prepare } =
      usePythonEnvironment({ enabled });
   const [dismissed, setDismissed] = useState(
      () => window.localStorage.getItem(DISMISSED_KEY) === "1"
   );
   const navigate = useNavigate();
   const { getGeneralRoutePath } = useRoute();
   const ui = useUiFeedback();

   useEffect(() => {
      if (
         environment?.initialized &&
         window.localStorage.getItem(DISMISSED_KEY)
      ) {
         window.localStorage.removeItem(DISMISSED_KEY);
      }
   }, [environment?.initialized]);

   if (
      !enabled ||
      isLoading ||
      dismissed ||
      !environment ||
      !environment.available ||
      environment.initialized
   ) {
      return null;
   }

   const handlePrepare = async () => {
      try {
         await prepare();
         ui.success("Python environment prepared successfully.");
      } catch (error) {
         ui.error(
            error instanceof Error
               ? error.message
               : "Failed to prepare Python environment."
         );
      }
   };

   const handleClose = () => {
      setDismissed(true);
      window.localStorage.setItem(DISMISSED_KEY, "1");
   };

   return (
      <Alert
         style={{ marginBottom: 16 }}
         type="warning"
         showIcon
         closable
         onClose={handleClose}
         message="Set up your Python environment"
         description="Chats and Python blocks stay unavailable until the managed Python runtime is prepared."
         action={
            <Space direction="vertical" size="small">
               <Button
                  type="primary"
                  size="small"
                  icon={<CodeOutlined />}
                  loading={isPreparing}
                  onClick={() => void handlePrepare()}
               >
                  Prepare environment
               </Button>
               <Button
                  size="small"
                  type="text"
                  onClick={() =>
                     navigate(
                        getGeneralRoutePath(RouteNames.USER_PYTHON_ENVIRONMENT)
                     )
                  }
               >
                  View details
               </Button>
            </Space>
         }
      />
   );
};

export default PythonEnvironmentBanner;
