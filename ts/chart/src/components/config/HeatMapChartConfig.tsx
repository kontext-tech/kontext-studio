import type { HeatMapConfig as HeatMapConfigType } from "@kontext-labs/schema";
import { MARK_TYPES } from "@kontext-labs/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Format mark type for display
 */
const formatMarkType = (markType: string): string => {
   if (markType === "auto") return "Auto";
   if (markType === "lineX") return "Line X";
   if (markType === "lineY") return "Line Y";
   if (markType === "rangeX") return "Range X";
   if (markType === "rangeY") return "Range Y";
   if (markType === "wordCloud") return "Word Cloud";
   if (markType === "forceGraph") return "Force Graph";
   // Convert camelCase to Title Case
   return markType
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (str) => str.toUpperCase())
      .trim();
};

/**
 * Heat Map Chart Configuration Component
 */
export const HeatMapChartConfig: React.FC<
   BaseChartConfigProps<HeatMapConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Heat maps visualize data through colors and sizes to show patterns
            and relationships in matrix data
         </Text>

         {/* X Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  X Axis <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.xField as string}
                  onChange={(value: string) => onChange({ xField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select X field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Y Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Y Axis <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.yField as string}
                  onChange={(value: string) => onChange({ yField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select Y field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Color Field (Required) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Color <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.colorField as string}
                  onChange={(value: string) => onChange({ colorField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select color field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Size Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Size</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.sizeField as string}
                  onChange={(value?: string) =>
                     onChange({ sizeField: value === "" ? undefined : value })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select size field (optional)"
                  allowClear
               >
                  <Option value="">None</Option>
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Shape Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Shape</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.shapeField as string}
                  onChange={(value?: string) =>
                     onChange({ shapeField: value === "" ? undefined : value })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select shape field (optional)"
                  allowClear
               >
                  <Option value="">None</Option>
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Mark Type (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Mark Type</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.mark}
                  onChange={(value?: string) =>
                     onChange({
                        mark:
                           value === ""
                              ? undefined
                              : (value as HeatMapConfigType["mark"])
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select mark type (optional)"
                  allowClear
               >
                  <Option value="">Auto</Option>
                  {MARK_TYPES.filter((type) => type !== "auto").map(
                     (markType) => (
                        <Option key={markType} value={markType}>
                           {formatMarkType(markType)}
                        </Option>
                     )
                  )}
               </Select>
            </Col>
         </Row>

         {/* Number Format */}
         <NumberFormatSelect
            value={config.numberFormat}
            onChange={(value) => onChange({ numberFormat: value })}
            disabled={readonly}
         />
      </Space>
   );
};
