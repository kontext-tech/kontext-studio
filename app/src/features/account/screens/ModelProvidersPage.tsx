import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { RouteNames } from "@/types";
import {
   ModelProviderSettingsPanel,
   type ModelProviderSettingsPanelHandle
} from "@kontext-tech/chat";
import { PlusOutlined } from "@kontext-tech/icons";
import { ProjectService } from "@kontext-tech/project";
import { useService } from "@kontext-tech/app-runtime/hooks";
import { useUiFeedback } from "@kontext-tech/ui";
import { Button, Typography } from "antd";
import { useCallback, useRef } from "react";

const getFoundationModelLoadError = (error?: {
   title?: string;
   messages?: string[];
}) =>
   error?.messages?.[0] ||
   error?.title ||
   "Failed to load the curated foundation model catalog.";

const ModelProvidersPage = () => {
   const apiErrorHandler = useApiErrorHandler();
   const ui = useUiFeedback();
   const projectService = useService(ProjectService, apiErrorHandler);
   const panelRef = useRef<ModelProviderSettingsPanelHandle>(null);
   const loadFoundationModels = useCallback(async () => {
      const response = await projectService.getFoundationModels();
      if (!response.succeed || !response.data) {
         throw new Error(getFoundationModelLoadError(response.error));
      }

      return response.data;
   }, [projectService]);

   return (
      <PageContainer
         title="LLM Providers"
         description="Configure the model providers available to your local Kontext runtime"
         routeName={RouteNames.USER_MODEL_CONNECTIONS}
         type="website"
         showBreadcrumb={false}
         actions={
            <Button
               type="primary"
               icon={<PlusOutlined />}
               onClick={() => panelRef.current?.openAddConnection()}
            >
               Add Provider
            </Button>
         }
         subContent={
            <Typography.Paragraph
               type="secondary"
               style={{ marginBottom: 0, maxWidth: 680 }}
            >
               Manage the provider connections your local runtime uses for chats
               and other AI features.
            </Typography.Paragraph>
         }
      >
         <ModelProviderSettingsPanel
            ref={panelRef}
            errorHandler={apiErrorHandler}
            loadFoundationModels={loadFoundationModels}
            ui={ui}
            showDescription={false}
            displayMode="plain"
         />
      </PageContainer>
   );
};

export default ModelProvidersPage;
