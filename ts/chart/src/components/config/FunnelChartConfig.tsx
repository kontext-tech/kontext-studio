import type { FunnelChartConfig as FunnelChartConfigType } from "@kontext-labs/schema";
import { Col, Row, Select, Space, Switch, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Funnel Chart Configuration Component
 */
export const FunnelChartConfig: React.FC<
   BaseChartConfigProps<FunnelChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Funnel charts visualize data flow through stages, showing conversion
            rates between steps
         </Text>
         {/* X Field - Stage/Category field */}
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
         {/* Y Field - Value field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Value Field <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.yField as string}
                  onChange={(value: string) => onChange({ yField: value })}
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
         {/* Compare Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Compare Field</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.compareField as string}
                  onChange={(value?: string) =>
                     onChange({
                        compareField: value === "" ? undefined : value
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select compare field (optional)"
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
         {/* Series Field (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Series Field</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.seriesField as string}
                  onChange={(value?: string) =>
                     onChange({ seriesField: value === "" ? undefined : value })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select series field (optional)"
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
         {/* Is Transposed (Optional) */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Transpose</Text>
            </Col>
            <Col span={16}>
               <Switch
                  checked={config.isTransposed ?? false}
                  onChange={(checked: boolean) =>
                     onChange({ isTransposed: checked })
                  }
                  disabled={readonly}
               />
               <Text type="secondary" style={{ marginLeft: 8 }}>
                  Rotate the funnel chart
               </Text>
            </Col>
         </Row>
         {/* Number Format */}
         <NumberFormatSelect
            value={config.numberFormat}
            onChange={(value) => onChange({ numberFormat: value })}
            disabled={readonly}
         />{" "}
      </Space>
   );
};
