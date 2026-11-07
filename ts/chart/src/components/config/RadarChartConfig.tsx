import {
   RadarCoordinateTypeSchema,
   type RadarChartConfig as RadarChartConfigType
} from "@kontext-tech/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

const COORDINATE_TYPES = Object.values(RadarCoordinateTypeSchema.enum).filter(
   (coordinateType) => coordinateType === "polar"
);

export const RadarChartConfig: React.FC<
   BaseChartConfigProps<RadarChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Radar charts compare values across categories around a circular
            axis.
         </Text>
         <Text type="secondary">
            Polar is currently used for reliable radar rendering in our chart
            runtime.
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
               <Text strong>Coordinate</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={
                     config.coordinateType === "radar"
                        ? "polar"
                        : (config.coordinateType ?? "polar")
                  }
                  onChange={(value: RadarChartConfigType["coordinateType"]) =>
                     onChange({ coordinateType: value || "polar" })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
               >
                  {COORDINATE_TYPES.map((coordinateType) => (
                     <Option key={coordinateType} value={coordinateType}>
                        Polar
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         <NumberFormatSelect
            value={config.numberFormat}
            onChange={(value) => onChange({ numberFormat: value })}
            disabled={readonly}
         />
      </Space>
   );
};
