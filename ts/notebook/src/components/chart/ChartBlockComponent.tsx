import {
   ChartBuilder,
   ChartFactory,
   type ChartConfig,
   type ChartType
} from "@kontext-tech/chart";
import { extractChartDataRows, inferChartFields } from "@kontext-tech/common";
import {
   ChartLineOutlined,
   EditOutlined,
   SettingOutlined
} from "@kontext-tech/icons";
import type { ChartBlockData } from "@kontext-tech/schema";
import { useTheme } from "@kontext-tech/theme";
import {
   Alert,
   Button,
   Card,
   Empty,
   Flex,
   Modal,
   Tooltip,
   Typography,
   theme
} from "antd";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
   useNotebookDataReference,
   useNotebookInlineData
} from "../../hooks/useInlineData";
import { InlineDataSelector } from "./InlineDataSelector";

const { useToken } = theme;
const { Text } = Typography;

interface ChartBlockComponentProps {
   /** The chart block data */
   data: ChartBlockData;
   /** The block ID for store updates */
   blockId: string;
   /** Callback when chart configuration changes */
   onChange: (data: ChartBlockData) => void;
   /** Whether the wizard is readonly */
   readonly?: boolean;
   /** Optional CSS class name */
   className?: string;
   /** Optional notebook instanceId for multi-instance support */
   instanceId?: string;
}

/**
 * Chart Block Component for notebook - simplified wrapper around charts package
 * Shows initial state, configured charts, and handles configuration in a modal
 */
export const ChartBlockComponent: React.FC<ChartBlockComponentProps> = ({
   data,
   blockId,
   onChange,
   readonly = false,
   className,
   instanceId
}) => {
   // Memoize theme token to prevent unnecessary re-renders
   const token = useToken().token;
   const [isModalOpen, setIsModalOpen] = useState(false);
   const [selectedDataId, setSelectedDataId] = useState<string | undefined>(
      data.dataRef?.dataId
   );
   const [tempConfig, setTempConfig] = useState<ChartBlockData>(() => ({
      ...data
   }));

   // Get dark mode setting from theme context (synced with shared root)
   // This ensures isDarkMode and token are always consistent to avoid race conditions
   const { isDarkMode } = useTheme();

   // Load data from remote source if referenced
   const {
      data: table,
      isLoading: isLoadingRemote,
      error: remoteError
   } = useNotebookDataReference(data.dataRef);

   // Load data for configured chart (prioritizes embedded data)
   const chartData = useMemo(
      () => extractChartDataRows(data, table),
      [data, table]
   );
   const isLoadingChartData = isLoadingRemote;
   const chartDataError = remoteError;

   // Load data for modal preview
   const modalSpec = useMemo(
      () => ({
         config: tempConfig.config,
         inlineData: tempConfig.inlineData,
         dataRef: selectedDataId ? { dataId: selectedDataId } : undefined
      }),
      [tempConfig.config, tempConfig.inlineData, selectedDataId]
   );

   const {
      data: modalTable,
      isLoading: isLoadingModalRemote,
      error: modalRemoteError
   } = useNotebookInlineData(selectedDataId);

   const modalChartData = useMemo(
      () => extractChartDataRows(modalSpec, modalTable),
      [modalSpec, modalTable]
   );
   const isLoadingModalData = isLoadingModalRemote;
   const modalDataError = modalRemoteError;

   // Check if the chart is configured
   const isConfigured = !!data.config.chartType;

   // Sync tempConfig with data prop when it changes (but not when modal is open)
   useEffect(() => {
      if (!isModalOpen) {
         // eslint-disable-next-line react-hooks/set-state-in-effect
         setTempConfig({ ...data });
      }
   }, [data, isModalOpen]);

   const handleOpenModal = useCallback(() => {
      setTempConfig({ ...data });
      setSelectedDataId(data.dataRef?.dataId);
      setIsModalOpen(true);
   }, [data]);

   const handleReconnectDataTable = () => {
      setTempConfig({ ...data });
      setSelectedDataId(undefined); // Clear selection to show data table selector
      setIsModalOpen(true);
   };

   const handleCancel = () => {
      setIsModalOpen(false);
   };

   const handleSave = () => {
      onChange(tempConfig);
      setIsModalOpen(false);
   };

   const handleConfigChange = (newData: {
      chartType: ChartType;
      chartConfig: ChartConfig;
   }) => {
      // Convert the new data structure to ChartBlockData
      // Use the selected data ID
      const dataRef = selectedDataId
         ? {
              dataId: selectedDataId
           }
         : undefined;

      // If the chart type changed and we have modalChartData, we can auto-infer fields if they are missing
      const newConfig: Record<string, unknown> = { ...newData.chartConfig };
      if (
         newData.chartType !== tempConfig.config.chartType &&
         modalTable &&
         modalTable.columns &&
         modalTable.columns.length > 0
      ) {
         // Map DataFrame fields for inference
         const columns = modalTable.columns.map(
            (f: { name: string; type: string }) => ({
               name: f.name,
               type: f.type || "string"
            })
         );

         const inferredFields = inferChartFields(newData.chartType, columns);

         if (!newConfig.xField && inferredFields.xField) {
            newConfig.xField = inferredFields.xField;
         }
         if (!newConfig.yField && inferredFields.yField) {
            newConfig.yField = inferredFields.yField;
         }
         if (!newConfig.binField && inferredFields.binField) {
            newConfig.binField = inferredFields.binField;
         }
         if (!newConfig.colorField && inferredFields.colorField) {
            newConfig.colorField = inferredFields.colorField;
         }
         if (!newConfig.angleField && inferredFields.angleField) {
            newConfig.angleField = inferredFields.angleField;
         }
      }

      const chartBlockData: ChartBlockData = {
         config: newConfig as ChartConfig,
         dataRef
      };
      setTempConfig(chartBlockData);
   };

   // Memoize the chart component and its config to avoid unnecessary re-renders
   // during stream updates that don't affect this chart's specific data or config.
   const chartElement = useMemo(() => {
      if (!isConfigured || !data.config.chartType) return null;
      if (isLoadingChartData) return null;
      if (chartDataError || !chartData || chartData.length === 0) return null;

      return (
         <ChartFactory
            config={{ ...data.config, data: chartData }}
            isDarkMode={isDarkMode}
            extra={
               !readonly && (
                  <Tooltip title="Edit Chart">
                     <Button
                        onClick={handleOpenModal}
                        icon={<EditOutlined />}
                        size="small"
                        type="text"
                     />
                  </Tooltip>
               )
            }
         />
      );
   }, [
      isConfigured,
      data.config,
      chartData,
      isDarkMode,
      isLoadingChartData,
      chartDataError,
      readonly,
      handleOpenModal
   ]);

   return (
      <>
         <Card
            className={className}
            variant="borderless"
            style={{
               backgroundColor: isConfigured
                  ? token.colorBgContainer
                  : token.colorBgLayout
            }}
            styles={{
               body: {
                  padding:
                     isConfigured && data.config.chartType ? 0 : token.paddingLG
               }
            }}
            key={`chart-block-${blockId}-${isDarkMode ? "dark" : "light"}`}
         >
            {isConfigured && data.config.chartType ? (
               <div style={{ position: "relative" }}>
                  {/* Show chart preview using charts package */}
                  {isLoadingChartData ? (
                     <Flex
                        align="center"
                        justify="center"
                        style={{ minHeight: 200 }}
                     >
                        <Text type="secondary">Loading chart data...</Text>
                     </Flex>
                  ) : chartDataError ? (
                     <Alert
                        type="warning"
                        showIcon
                        banner
                        title="Data Table Not Available"
                        description="The data table for this chart is no longer available or was not found."
                        action={
                           !readonly && (
                              <Button
                                 size="small"
                                 type="primary"
                                 shape="round"
                                 onClick={handleReconnectDataTable}
                              >
                                 Select Data Table
                              </Button>
                           )
                        }
                        style={{ margin: 0 }}
                     />
                  ) : chartData && chartData.length > 0 ? (
                     chartElement
                  ) : (
                     <Alert
                        type="info"
                        showIcon
                        banner
                        title="No Data Table Selected"
                        description="This chart needs to be connected to a data table to display data."
                        action={
                           !readonly && (
                              <Button
                                 size="small"
                                 type="primary"
                                 shape="round"
                                 onClick={handleReconnectDataTable}
                              >
                                 Select Data Table
                              </Button>
                           )
                        }
                        style={{ margin: 0 }}
                     />
                  )}{" "}
               </div>
            ) : (
               <Flex
                  vertical
                  align="center"
                  justify="center"
                  gap="middle"
                  style={{ minHeight: 200 }}
               >
                  <Empty
                     image={<ChartLineOutlined style={{ fontSize: 48 }} />}
                     description={
                        <Text strong>This chart is not configured yet.</Text>
                     }
                  />
                  {!readonly && (
                     <Button
                        type="primary"
                        onClick={handleOpenModal}
                        disabled={readonly}
                        icon={<ChartLineOutlined />}
                     >
                        Configure Chart
                     </Button>
                  )}
               </Flex>
            )}
         </Card>

         {/* Configuration Modal */}
         <Modal
            title={
               <Flex gap="small" align="center">
                  <SettingOutlined />
                  <Text>
                     {!selectedDataId && modalDataError
                        ? "Select New Data Table"
                        : selectedDataId
                          ? "Configure Chart"
                          : "Create Chart - Select Data Table"}
                  </Text>
               </Flex>
            }
            open={isModalOpen}
            onCancel={handleCancel}
            width={1000}
            destroyOnHidden
            footer={
               <Flex justify="end" gap="small">
                  <Button onClick={handleCancel}>Cancel</Button>
                  <Button
                     type="primary"
                     onClick={handleSave}
                     disabled={!selectedDataId}
                  >
                     Save Chart
                  </Button>
               </Flex>
            }
            afterClose={() => {
               // Reset temp config after modal closes
               setTempConfig({ ...data });
            }}
         >
            <div style={{ minHeight: 400 }}>
               {!selectedDataId ? (
                  // Data table selection step
                  <InlineDataSelector
                     selectedInlineDataId={selectedDataId}
                     onInlineDataChange={setSelectedDataId}
                     readonly={readonly}
                     instanceId={instanceId}
                  />
               ) : isLoadingModalData ? (
                  // Loading state while fetching the data table
                  <Flex
                     align="center"
                     justify="center"
                     style={{ minHeight: 400 }}
                  >
                     <Text type="secondary">Loading data table...</Text>
                  </Flex>
               ) : modalDataError ? (
                  // Error state - show the selector to pick a different table
                  <>
                     <Alert
                        type="error"
                        showIcon
                        banner
                        title="Failed to Load Data Table"
                        description={
                           modalDataError.message ||
                           "The selected data table is no longer available. Please select a different data table."
                        }
                        style={{ marginBottom: token.marginLG }}
                     />
                     <InlineDataSelector
                        selectedInlineDataId={selectedDataId}
                        onInlineDataChange={setSelectedDataId}
                        readonly={readonly}
                        instanceId={instanceId}
                     />
                  </>
               ) : (
                  // Chart Configuration Step
                  <ChartBuilder
                     data={{
                        chartType: tempConfig.config.chartType,
                        chartConfig: tempConfig.config
                     }}
                     chartData={modalChartData}
                     readonly={readonly}
                     isDarkMode={isDarkMode}
                     onChange={handleConfigChange}
                  />
               )}
            </div>
         </Modal>
      </>
   );
};
