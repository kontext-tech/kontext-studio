import type { HistogramChartConfig as HistogramChartConfigType } from "@kontext-tech/schema";
import { Col, InputNumber, Row, Select, Space, Typography } from "antd";
import React from "react";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

export const HistogramChartConfig: React.FC<
   BaseChartConfigProps<HistogramChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Histograms group a numeric field into bins to show its distribution.
         </Text>

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Bin Field <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.binField}
                  onChange={(value: string) => onChange({ binField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select numeric field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Series</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.colorField}
                  onChange={(value?: string) =>
                     onChange({ colorField: value === "" ? undefined : value })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select grouping field"
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

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Bin Width</Text>
            </Col>
            <Col span={16}>
               <InputNumber
                  value={config.binWidth}
                  onChange={(value) =>
                     onChange({
                        binWidth: typeof value === "number" ? value : undefined
                     })
                  }
                  style={{ width: "100%" }}
                  min={0}
                  step={1}
                  disabled={readonly}
                  placeholder="Optional bin width"
               />
            </Col>
         </Row>

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Bin Count</Text>
            </Col>
            <Col span={16}>
               <InputNumber
                  value={config.binNumber}
                  onChange={(value) =>
                     onChange({
                        binNumber:
                           typeof value === "number"
                              ? Math.trunc(value)
                              : undefined
                     })
                  }
                  style={{ width: "100%" }}
                  min={1}
                  step={1}
                  disabled={readonly}
                  placeholder="Optional bin count"
               />
            </Col>
         </Row>
      </Space>
   );
};
