import {
   BoxChartTypeSchema,
   type BoxChartConfig as BoxChartConfigType
} from "@kontext-labs/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

const BOX_TYPES = Object.values(BoxChartTypeSchema.enum);

export const BoxChartConfig: React.FC<
   BaseChartConfigProps<BoxChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Box charts summarize the spread of values across categories.
         </Text>

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Category <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.xField}
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

         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Value <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.yField}
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
               <Text strong>Box Type</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.boxType || "box"}
                  onChange={(value: BoxChartConfigType["boxType"]) =>
                     onChange({ boxType: value || "box" })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
               >
                  {BOX_TYPES.map((boxType) => (
                     <Option key={boxType} value={boxType}>
                        {boxType === "box" ? "Raw Data" : "Preprocessed"}
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>
      </Space>
   );
};
