import type {
   AggregateMethod,
   BarChartConfig as BarChartConfigType
} from "@kontext-tech/schema";
import { Col, Row, Select, Space, Switch, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Bar Chart Configuration Component
 */
export const BarChartConfig: React.FC<
   BaseChartConfigProps<BarChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Bar charts display categorical data with horizontal bars. Use
            colorField to group data by series.
         </Text>

         {/* X Field (Category) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Category <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.xField as string}
                  onChange={(value: string) => onChange({ xField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select category field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {/* Y Field (Value) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Value <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.yField as string}
                  onChange={(value: string) =>
                     onChange({
                        yField: value,
                        // Default to sum if not set
                        aggregate: (config.aggregate ||
                           "sum") as AggregateMethod
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select value field"
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
                  value={config.aggregate || "sum"}
                  onChange={(value: string) =>
                     onChange({ aggregate: value as AggregateMethod })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
               >
                  <Option value="sum">Sum</Option>
                  <Option value="avg">Average</Option>
                  <Option value="count">Count</Option>
                  <Option value="max">Maximum</Option>
                  <Option value="min">Minimum</Option>
                  <Option value="none">None (Raw Data)</Option>
               </Select>
            </Col>
         </Row>

         {/* Color Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Series (Color)</Text>
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

         {/* Stack Toggle */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Stack Series</Text>
            </Col>
            <Col span={16}>
               <Space align="center">
                  <Switch
                     checked={config.stack === true}
                     onChange={(checked: boolean) =>
                        onChange({ stack: checked ? true : false })
                     }
                     disabled={readonly}
                  />
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Stack series data on top of each other
                  </Text>
               </Space>
            </Col>
         </Row>

         {/* Group Toggle */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Group Series</Text>
            </Col>
            <Col span={16}>
               <Space align="center">
                  <Switch
                     checked={config.group === true}
                     onChange={(checked: boolean) =>
                        onChange({ group: checked })
                     }
                     disabled={readonly}
                  />
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Display series side by side
                  </Text>
               </Space>
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
