import type { StockChartConfig as StockChartConfigType } from "@kontext-labs/schema";
import { Col, Row, Select, Space, Typography } from "antd";
import React from "react";
import { NumberFormatSelect } from "../NumberFormatSelect";
import type { BaseChartConfigProps } from "./configTypes";

const { Text } = Typography;
const { Option } = Select;

function getYFieldTuple(
   yField: StockChartConfigType["yField"] | undefined
): [
   string | undefined,
   string | undefined,
   string | undefined,
   string | undefined
] {
   return [yField?.[0], yField?.[1], yField?.[2], yField?.[3]];
}

function updateTupleValue(
   current: StockChartConfigType["yField"] | undefined,
   index: number,
   value: string
): StockChartConfigType["yField"] {
   const tuple = getYFieldTuple(current);
   tuple[index] = value;
   return tuple as StockChartConfigType["yField"];
}

export const StockChartConfig: React.FC<
   BaseChartConfigProps<StockChartConfigType>
> = ({ config, availableColumns, onChange, readonly = false }) => {
   const [openField, closeField, lowField, highField] = getYFieldTuple(
      config.yField
   );

   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
         <Text type="secondary">
            Stock charts render open, close, low, and high values over time.
         </Text>

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
                  placeholder="Select time field"
               >
                  {availableColumns.map((col) => (
                     <Option key={col.name} value={col.name}>
                        {col.name} ({col.type})
                     </Option>
                  ))}
               </Select>
            </Col>
         </Row>

         {[
            ["Open", openField, 0],
            ["Close", closeField, 1],
            ["Low", lowField, 2],
            ["High", highField, 3]
         ].map(([label, value, index]) => (
            <Row key={label} align="middle" gutter={[8, 0]}>
               <Col span={8}>
                  <Text strong>
                     {label} <Text type="danger">*</Text>
                  </Text>
               </Col>
               <Col span={16}>
                  <Select
                     value={value as string | undefined}
                     onChange={(nextValue: string) =>
                        onChange({
                           yField: updateTupleValue(
                              config.yField,
                              index as number,
                              nextValue
                           )
                        })
                     }
                     style={{ width: "100%" }}
                     disabled={readonly}
                     placeholder={`Select ${String(label).toLowerCase()} field`}
                  >
                     {availableColumns.map((col) => (
                        <Option key={col.name} value={col.name}>
                           {col.name} ({col.type})
                        </Option>
                     ))}
                  </Select>
               </Col>
            </Row>
         ))}

         <NumberFormatSelect
            value={config.numberFormat}
            onChange={(value) => onChange({ numberFormat: value })}
            disabled={readonly}
         />
      </Space>
   );
};
