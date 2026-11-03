import { Alert, Card, Space, Typography } from "antd";

import type {
   CatalogConnection,
   CatalogProviderDefinition
} from "@kontext-tech/schema";

import {
   getAuthTypeLabel,
   getExecutionModeLabel,
   type CatalogFormValues
} from "./formConfig";

type DataSourceReviewPanelProps = {
   values?: Partial<CatalogFormValues>;
   provider?: CatalogProviderDefinition;
   editingConnection?: CatalogConnection | null;
};

const getReviewLocationLabel = (values?: Partial<CatalogFormValues>) =>
   values?.databasePath ||
   [values?.host, values?.databaseName || values?.serviceName]
      .filter(Boolean)
      .join(" / ") ||
   "Connection details will be saved";

const DataSourceReviewPanel = ({
   values,
   provider,
   editingConnection
}: DataSourceReviewPanelProps) => (
   <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Alert
         type="info"
         showIcon
         title="Review this data source before saving"
         description="You can go back to adjust any connection or secret details before creating the source."
      />

      <Card size="small">
         <Space orientation="vertical" size="small" style={{ width: "100%" }}>
            <Typography.Text strong>
               {values?.displayName ||
                  provider?.displayName ||
                  "Unnamed data source"}
            </Typography.Text>
            <Typography.Text type="secondary">
               {provider?.displayName || "Provider not selected"}
            </Typography.Text>
            <Typography.Text type="secondary">
               {getReviewLocationLabel(values)}
            </Typography.Text>
            <Typography.Text type="secondary">
               Authentication:{" "}
               {getAuthTypeLabel(values?.authType || provider?.authTypes[0])}
            </Typography.Text>
            <Typography.Text type="secondary">
               Execution:{" "}
               {getExecutionModeLabel(
                  values?.executionMode || provider?.executionModes[0]
               ) || "Default"}
            </Typography.Text>
            {values?.defaultNamespace && (
               <Typography.Text type="secondary">
                  Default namespace: {values.defaultNamespace}
               </Typography.Text>
            )}
            <Typography.Text type="secondary">
               Secret update:{" "}
               {values?.secretValue
                  ? "A new secret will be stored"
                  : editingConnection?.secretConfigured
                    ? "Keep existing secret"
                    : "No secret value provided"}
            </Typography.Text>
         </Space>
      </Card>
   </Space>
);

export default DataSourceReviewPanel;
