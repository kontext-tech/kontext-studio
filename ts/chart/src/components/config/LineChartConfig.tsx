import type {
   AggregateMethod,
   LineChartConfig as LineChartConfigType
} from "@kontext-tech/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Line Chart Configuration Component
 */
export const LineChartConfig: React.FC<
   BaseChartConfigProps<LineChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Line charts show trends over time or continuous data
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

         {/* Aggregation Method */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Aggregation</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.aggregate || "none"}
                  onChange={(value: string) =>
                     onChange({ aggregate: value as AggregateMethod })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
               >
                  <Option value="none">None (Raw Data)</Option>
                  <Option value="sum">Sum</Option>
                  <Option value="avg">Average</Option>
                  <Option value="count">Count</Option>
                  <Option value="max">Maximum</Option>
                  <Option value="min">Minimum</Option>
               </Select>
            </Col>
         </Row>

         {/* Color Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Series</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.colorField as string}
                  onChange={(value?: string) =>
                     onChange({ colorField: value === "" ? undefined : value })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select color field (optional)"
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

         {/* Number Format */}
         <NumberFormatSelect
            value={config.numberFormat}
            onChange={(value) => onChange({ numberFormat: value })}
            disabled={readonly}
         />
      </Space>
   );
};
