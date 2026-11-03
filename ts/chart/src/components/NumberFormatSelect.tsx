import { NumberFormat } from "@kontext-tech/schema";
import { Select, Typography } from "antd";
import React from "react";

const { Text } = Typography;
const { Option } = Select;

export interface NumberFormatSelectProps {
   value?: NumberFormat;
   onChange: (value: NumberFormat) => void;
   disabled?: boolean;
}

export const NumberFormatSelect: React.FC<NumberFormatSelectProps> = ({
   value = "thousands",
   onChange,
   disabled = false
}) => {
   return (
      <div>
         <Text strong>Number Format</Text>
         <br />
         <Select
            value={value}
            onChange={onChange}
            style={{ width: "100%", marginTop: 8 }}
            disabled={disabled}
         >
            <Option value="short">Auto (Short)</Option>
            <Option value="none">Standard (Commas)</Option>
            <Option value="thousands">Thousands (K)</Option>
            <Option value="millions">Millions (M)</Option>
            <Option value="billions">Billions (B)</Option>
         </Select>
      </div>
   );
};
