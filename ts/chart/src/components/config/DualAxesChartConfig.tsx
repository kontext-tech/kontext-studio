import type {
   AggregateMethod,
   DualAxesChartConfig as DualAxesChartConfigType,
   DualAxesChartType
} from "@kontext-labs/schema";
import { Col, Row, Select, Space, Switch, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

/**
 * Dual Axes Chart Configuration Component
 * Uses flattened structure for easier UI management
 */
export const DualAxesChartConfig: React.FC<
   BaseChartConfigProps<DualAxesChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Display two different data series on separate Y axes. Left axis uses
            bars/columns, right axis uses lines.
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
                  value={config.xField}
                  onChange={(value: string) => onChange({ xField: value })}
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select X field"
               >
                  {availableColumns.map((col) => (
                     <Option key={`x-field-${col.name}`} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>
         {/* Left Y Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Left Y Axis <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Space
                  orientation="vertical"
                  style={{ width: "100%" }}
                  size="small"
               >
                  <Select
                     value={config.leftYField}
                     onChange={(value: string) =>
                        onChange({
                           leftYField: value,
                           // Default to sum if not set
                           leftAggregate: (config.leftAggregate ||
                              "sum") as AggregateMethod
                        })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                     placeholder="Select left Y field"
                     allowClear
                  >
                     {availableColumns.map((col) => (
                        <Option
                           key={`left-y-field-${col.name}`}
                           value={col.name}
                        >
                           {col.name} ({col.type})
                        </Option>
                     ))}
                  </Select>
                  <Select
                     value={config.leftAggregate || "sum"}
                     onChange={(value: string) =>
                        onChange({ leftAggregate: value as AggregateMethod })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                     placeholder="Select left aggregation"
                  >
                     <Option value="sum">Sum</Option>
                     <Option value="avg">Average</Option>
                     <Option value="count">Count</Option>
                     <Option value="max">Maximum</Option>
                     <Option value="min">Minimum</Option>
                     <Option value="none">None</Option>
                  </Select>
                  <Select
                     value={config.leftChartType || "interval"}
                     onChange={(value: DualAxesChartType) =>
                        onChange({ leftChartType: value })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                  >
                     <Option value="interval">Bar/Column</Option>
                     <Option value="line">Line</Option>
                     <Option value="area">Area</Option>
                  </Select>
               </Space>
            </Col>
         </Row>
         {/* Left Color Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Left Series (Color)</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.leftColorField}
                  onChange={(value?: string) =>
                     onChange({
                        leftColorField: value === "" ? undefined : value
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select left color field (optional)"
                  allowClear
               >
                  <Option value="">None</Option>
                  {availableColumns.map((col) => (
                     <Option key={`left-color-${col.name}`} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>
         {/* Left Stack Toggle */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Left Stack</Text>
            </Col>
            <Col span={16}>
               <Space align="center">
                  <Switch
                     checked={config.leftStack === true}
                     onChange={(checked: boolean) =>
                        onChange({ leftStack: checked ? true : false })
                     }
                     disabled={
                        readonly ||
                        (config.leftChartType !== "interval" &&
                           config.leftChartType !== "area")
                     }
                  />
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Stack left axis data (interval/area only)
                  </Text>
               </Space>
            </Col>
         </Row>
         {/* Right Y Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>
                  Right Y Axis <Text type="danger">*</Text>
               </Text>
            </Col>
            <Col span={16}>
               <Space
                  orientation="vertical"
                  style={{ width: "100%" }}
                  size="small"
               >
                  <Select
                     value={config.rightYField}
                     onChange={(value: string) =>
                        onChange({
                           rightYField: value,
                           // Default to sum if not set
                           rightAggregate: (config.rightAggregate ||
                              "sum") as AggregateMethod
                        })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                     placeholder="Select right Y field"
                     allowClear
                  >
                     {availableColumns.map((col) => (
                        <Option
                           key={`right-y-field-${col.name}`}
                           value={col.name}
                        >
                           {col.name} ({col.type})
                        </Option>
                     ))}
                  </Select>
                  <Select
                     value={config.rightAggregate || "sum"}
                     onChange={(value: string) =>
                        onChange({ rightAggregate: value as AggregateMethod })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                     placeholder="Select right aggregation"
                  >
                     <Option value="sum">Sum</Option>
                     <Option value="avg">Average</Option>
                     <Option value="count">Count</Option>
                     <Option value="max">Maximum</Option>
                     <Option value="min">Minimum</Option>
                     <Option value="none">None</Option>
                  </Select>
                  <Select
                     value={config.rightChartType || "line"}
                     onChange={(value: DualAxesChartType) =>
                        onChange({ rightChartType: value })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                  >
                     <Option value="line">Line</Option>
                     <Option value="area">Area</Option>
                     <Option value="interval">Bar/Column</Option>
                  </Select>
               </Space>
            </Col>
         </Row>
         {/* Right Color Field */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Right Series (Color)</Text>
            </Col>
            <Col span={16}>
               <Select
                  value={config.rightColorField}
                  onChange={(value?: string) =>
                     onChange({
                        rightColorField: value === "" ? undefined : value
                     })
                  }
                  style={{ width: "100%" }}
                  disabled={readonly}
                  placeholder="Select right color field (optional)"
                  allowClear
               >
                  <Option value="">None</Option>
                  {availableColumns.map((col) => (
                     <Option key={`right-color-${col.name}`} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>
         {/* Right Stack Toggle */}
         <Row align="middle" gutter={[8, 0]}>
            <Col span={8}>
               <Text strong>Right Stack</Text>
            </Col>
            <Col span={16}>
               <Space align="center">
                  <Switch
                     checked={config.rightStack === true}
                     onChange={(checked: boolean) =>
                        onChange({ rightStack: checked ? true : false })
                     }
                     disabled={
                        readonly ||
                        (config.rightChartType !== "interval" &&
                           config.rightChartType !== "area")
                     }
                  />
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Stack right axis data (interval/area only)
                  </Text>
               </Space>
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
