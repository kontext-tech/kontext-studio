import type {
   AggregateMethod,
   PieChartConfig as PieChartConfigType
} from "@kontext-tech/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Pie Chart Configuration Component
 */
export const PieChartConfig: React.FC<
   BaseChartConfigProps<PieChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Pie charts show proportional data as slices of a circle. angleField
            defines the slice size (value), colorField defines the categories
            (type).
         </Text>

         {/* Angle Field (angleField) - Value field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Value Field <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.angleField as string}
                  onChange={(value: string) =>
                     onChange({
                        angleField: value,
                        // Default to sum for pie
                        aggregate: (config.aggregate ||
                           "sum") as AggregateMethod
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select value field (e.g., 'value')"
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

         {/* Color Field (colorField) - Category field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Category <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.colorField as string}
                  onChange={(value: string) => {
                     if (value === config.angleField) {
                        return;
                     }
                     onChange({ colorField: value });
                  }}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select category field (e.g., 'type')"
               >
                  {availableColumns.map((col) => (
                     <Option
                        key={col.name}
                        value={col.name}
                        disabled={col.name === config.angleField}
                     >
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
