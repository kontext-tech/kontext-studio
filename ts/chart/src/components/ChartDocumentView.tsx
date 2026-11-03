import { extractChartDataRows } from "@kontext-tech/common";
import { SaveOutlined } from "@kontext-tech/icons";
import QueryResultsView from "@kontext-tech/query/query-results";
import type {
   ChartDocument,
   DataTable,
   QueryResponse
} from "@kontext-tech/schema";
import { useTheme } from "@kontext-tech/theme";
import { LoadingSpinner, ProvenanceInfo } from "@kontext-tech/ui";
import { Alert, Button, Empty, Modal, Tabs, Tag } from "antd";
import { useMemo, useState } from "react";
import type { ChartConfig, ChartType } from "../types/chart";
import { resolveChartQueryResponse } from "../utils/chartQueryResponse";
import { ChartBuilder } from "./ChartBuilder";
import { ChartFactory } from "./ChartFactory";

export interface ChartDocumentViewProps {
   chart: ChartDocument;
   remoteTable?: DataTable;
   isRemoteDataLoading?: boolean;
   remoteDataError?: Error | null;
   readonly?: boolean;
   canEdit?: boolean;
   onSave?: (updatedChart: ChartDocument) => Promise<boolean>;
   isSaving?: boolean;
}

const ChartDocumentView: React.FC<ChartDocumentViewProps> = ({
   chart,
   remoteTable,
   isRemoteDataLoading = false,
   remoteDataError = null,
   readonly = false,
   canEdit = false,
   onSave,
   isSaving = false
}) => {
   const { isDarkMode } = useTheme();
   const [isEditing, setIsEditing] = useState(false);
   const [tempConfig, setTempConfig] = useState<ChartConfig | null>(null);

   const chartData = useMemo(
      () => extractChartDataRows(chart || undefined, remoteTable),
      [chart, remoteTable]
   );

   const isEmbedded = !!chart?.inlineData;
   const isChartDataLoading = isEmbedded ? false : isRemoteDataLoading;
   const chartDataError = isEmbedded ? undefined : remoteDataError;
   const isLoading = isChartDataLoading || isRemoteDataLoading;
   const error = chartDataError || remoteDataError;

   const queryResponse = useMemo<QueryResponse | null>(() => {
      return resolveChartQueryResponse(chart, remoteTable);
   }, [chart, remoteTable]);

   const handleEdit = () => {
      setTempConfig({ ...chart.config });
      setIsEditing(true);
   };

   const handleConfigChange = (data: {
      chartType: ChartType;
      chartConfig: ChartConfig;
   }) => {
      setTempConfig(data.chartConfig);
   };

   const handleSave = async () => {
      if (!tempConfig || !onSave) return;

      const updatedChart: ChartDocument = {
         ...chart,
         config: tempConfig
      };

      const success = await onSave(updatedChart);
      if (success) {
         setIsEditing(false);
      }
   };

   if (isLoading && !error) {
      return <LoadingSpinner size="large" style={{ height: "400px" }} />;
   }

   if (error) {
      return (
         <Alert
            title="Error Loading Chart Data"
            description={error.message}
            type="error"
            showIcon
            style={{ margin: "16px" }}
         />
      );
   }

   return (
      <div
         style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden"
         }}
      >
         <div
            style={{
               flex: 1,
               overflow: "hidden",
               display: "flex",
               flexDirection: "column"
            }}
         >
            <Tabs
               defaultActiveKey="chart"
               tabBarStyle={{
                  marginLeft: 16,
                  marginRight: 16,
                  marginBottom: 0
               }}
               style={{ height: "100%" }}
               items={[
                  {
                     key: "chart",
                     label: <span>Chart</span>,
                     children: (
                        <div
                           style={{
                              padding: "16px",
                              height: "100%",
                              overflow: "auto"
                           }}
                        >
                           <ChartFactory
                              config={{
                                 ...chart.config,
                                 data: chartData,
                                 title: chart.config.title || chart.name
                              }}
                              isDarkMode={isDarkMode}
                              extra={
                                 !readonly &&
                                 canEdit &&
                                 onSave && (
                                    <Button
                                       type="text"
                                       onClick={handleEdit}
                                       size="small"
                                    >
                                       Edit
                                    </Button>
                                 )
                              }
                           />
                        </div>
                     )
                  },
                  {
                     key: "data",
                     label: <span>Data</span>,
                     children: (
                        <div
                           style={{
                              padding: "16px",
                              height: "100%",
                              overflow: "hidden"
                           }}
                        >
                           {queryResponse ? (
                              <QueryResultsView response={queryResponse} />
                           ) : (
                              <Empty description="No underlying data available in this artifact" />
                           )}
                        </div>
                     )
                  },
                  {
                     key: "metadata",
                     label: <span>Metadata</span>,
                     children: (
                        <div
                           style={{
                              padding: "16px",
                              height: "100%",
                              overflow: "auto"
                           }}
                        >
                           <ProvenanceInfo
                              notebookId={chart.metadata?.notebookId}
                              querySessionId={chart.metadata?.querySessionId}
                              chatSessionId={chart.metadata?.chatSessionId}
                              sql={chart.dataRef?.code}
                              createdAt={chart.metadata?.createdAt}
                              extraItems={[
                                 ...(chart.metadata?.author
                                    ? [
                                         {
                                            key: "author",
                                            label: "Author",
                                            children: chart.metadata.author
                                         }
                                      ]
                                    : []),
                                 ...(chart.metadata?.modifiedAt
                                    ? [
                                         {
                                            key: "modifiedAt",
                                            label: "Modified",
                                            children: new Date(
                                               chart.metadata.modifiedAt
                                            ).toLocaleString()
                                         }
                                      ]
                                    : []),
                                 ...(chart.metadata?.version
                                    ? [
                                         {
                                            key: "version",
                                            label: "Version",
                                            children: chart.metadata.version
                                         }
                                      ]
                                    : [])
                              ]}
                           />
                           {chart.metadata?.description && (
                              <p style={{ marginTop: 16 }}>
                                 {chart.metadata.description}
                              </p>
                           )}
                           {chart.metadata?.tags?.length ? (
                              <div style={{ marginTop: 8 }}>
                                 {chart.metadata.tags.map((tag) => (
                                    <Tag key={tag}>{tag}</Tag>
                                 ))}
                              </div>
                           ) : null}
                        </div>
                     )
                  }
               ]}
            />
         </div>

         <Modal
            title="Edit Chart Configuration"
            open={isEditing}
            onCancel={() => !isSaving && setIsEditing(false)}
            onOk={handleSave}
            confirmLoading={isSaving}
            width={1000}
            destroyOnHidden
            okText="Save to File"
            okButtonProps={{ icon: <SaveOutlined /> }}
         >
            <div style={{ minHeight: 400, paddingTop: 16 }}>
               {tempConfig && (
                  <ChartBuilder
                     data={{
                        chartType: tempConfig.chartType,
                        chartConfig: tempConfig
                     }}
                     chartData={chartData}
                     isDarkMode={isDarkMode}
                     onChange={handleConfigChange}
                  />
               )}
            </div>
         </Modal>
      </div>
   );
};

export default ChartDocumentView;
