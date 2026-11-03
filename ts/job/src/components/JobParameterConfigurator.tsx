import {
   CodeOutlined,
   FormOutlined,
   InfoCircleOutlined
} from "@kontext-tech/icons";
import type { UnifiedJobParameterModel } from "@kontext-tech/schema";
import { JobParameterType } from "@kontext-tech/schema";
import {
   Alert,
   Button,
   Card,
   Input,
   InputNumber,
   Popover,
   Select,
   Space,
   Switch,
   Typography
} from "antd";
import React, { useEffect, useState } from "react";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface JobParameterConfiguratorProps {
   parameters: UnifiedJobParameterModel[];
   value?: string;
   onChange?: (value: string) => void;
   disabled?: boolean;
}

interface ParameterValues {
   [key: string]: string | number | boolean | Date | null | undefined;
}

const convertToSerializable = (
   values: ParameterValues
): Record<string, unknown> => {
   const result: Record<string, unknown> = {};

   for (const [key, value] of Object.entries(values)) {
      if (value instanceof Date) {
         result[key] = value.toISOString();
      } else if (value !== undefined && value !== null) {
         result[key] = value;
      }
   }

   return result;
};

const JobParameterConfigurator: React.FC<JobParameterConfiguratorProps> = ({
   parameters,
   value,
   onChange,
   disabled = false
}) => {
   const [parameterValues, setParameterValues] = useState<ParameterValues>({});
   const [mode, setMode] = useState<"form" | "json">("form");
   const [jsonValue, setJsonValue] = useState("");

   useEffect(() => {
      if (value) {
         try {
            const parsed = JSON.parse(value);
            // eslint-disable-next-line react-hooks/set-state-in-effect -- sync controlled value prop to local state
            setParameterValues(parsed);
            setJsonValue(JSON.stringify(parsed, null, 2));
         } catch {
            setJsonValue(value);
            setMode("json");
         }
      } else {
         const defaultValues: ParameterValues = {};
         parameters.forEach((parameter) => {
            const defaultValue = parameter.defaultValue;
            if (
               defaultValue !== undefined &&
               defaultValue !== null &&
               (typeof defaultValue === "string" ||
                  typeof defaultValue === "number" ||
                  typeof defaultValue === "boolean" ||
                  defaultValue instanceof Date)
            ) {
               defaultValues[parameter.name!] = defaultValue;
            }
         });
         setParameterValues(defaultValues);
         setJsonValue(
            JSON.stringify(convertToSerializable(defaultValues), null, 2)
         );
      }
   }, [value, parameters]);

   const handleValueChange = (parameterName: string, newValue: unknown) => {
      const nextValues = {
         ...parameterValues,
         [parameterName]: newValue as
            string | number | boolean | Date | null | undefined
      };
      setParameterValues(nextValues);

      const jsonString = JSON.stringify(
         convertToSerializable(nextValues),
         null,
         2
      );
      setJsonValue(jsonString);
      onChange?.(JSON.stringify(convertToSerializable(nextValues)));
   };

   const handleJsonChange = (jsonText: string) => {
      setJsonValue(jsonText);

      if (!jsonText.trim()) {
         setParameterValues({});
         onChange?.("");
         return;
      }

      try {
         const parsed = JSON.parse(jsonText);
         setParameterValues(parsed);
         onChange?.(jsonText);
      } catch {
         onChange?.(jsonText);
      }
   };

   const renderParameterInput = (
      parameter: UnifiedJobParameterModel,
      onInputChange: (value: unknown) => void,
      currentValue: unknown
   ) => {
      const { name, description, type, possibleValues } = parameter;
      const commonProps = {
         placeholder: description || `Enter ${name}`,
         disabled
      };

      switch (type) {
         case JobParameterType.Boolean:
            return (
               <Switch
                  {...commonProps}
                  checkedChildren="Yes"
                  unCheckedChildren="No"
                  checked={currentValue as boolean}
                  onChange={onInputChange}
               />
            );
         case JobParameterType.Integer:
            return (
               <InputNumber
                  {...commonProps}
                  style={{ width: "100%" }}
                  value={currentValue as number}
                  onChange={onInputChange}
               />
            );
         case JobParameterType.String:
         default: {
            if (possibleValues && possibleValues.length > 0) {
               return (
                  <Select
                     {...commonProps}
                     style={{ width: "100%" }}
                     value={currentValue as string}
                     onChange={onInputChange}
                  >
                     {possibleValues.map((option) => (
                        <Select.Option key={option} value={option}>
                           {option}
                        </Select.Option>
                     ))}
                  </Select>
               );
            }

            const maxLength = parameter.maxLength ?? undefined;
            if (!maxLength || maxLength > 100) {
               return (
                  <TextArea
                     {...commonProps}
                     rows={4}
                     showCount
                     maxLength={maxLength}
                     style={{ borderRadius: 8 }}
                     value={currentValue as string}
                     onChange={(event) => onInputChange(event.target.value)}
                  />
               );
            }

            return (
               <Input
                  {...commonProps}
                  maxLength={maxLength}
                  showCount
                  style={{ borderRadius: 8 }}
                  value={currentValue as string}
                  onChange={(event) => onInputChange(event.target.value)}
               />
            );
         }
      }
   };

   if (parameters.length === 0) {
      return null;
   }

   return (
      <div>
         <div style={{ marginBottom: 16 }}>
            <Space.Compact>
               <Button
                  type={mode === "form" ? "primary" : "default"}
                  icon={<FormOutlined />}
                  onClick={() => setMode("form")}
                  shape="round"
                  size="small"
               >
                  Form Builder
               </Button>
               <Button
                  type={mode === "json" ? "primary" : "default"}
                  icon={<CodeOutlined />}
                  onClick={() => setMode("json")}
                  shape="round"
                  size="small"
               >
                  JSON Editor
               </Button>
            </Space.Compact>
         </div>

         {mode === "form" ? (
            <Card
               size="small"
               title={
                  <Space>
                     <FormOutlined />
                     <span>Parameter Configuration</span>
                  </Space>
               }
            >
               <div style={{ padding: "8px 0" }}>
                  {parameters.map((parameter) => {
                     const helpContent = (
                        <div>
                           <Paragraph>
                              <Text strong>Type:</Text> {parameter.type}
                           </Paragraph>
                           {parameter.maxLength && (
                              <Paragraph>
                                 <Text strong>Max Length:</Text>{" "}
                                 {parameter.maxLength}
                              </Paragraph>
                           )}
                           {parameter.defaultValue !== undefined &&
                              parameter.defaultValue !== null && (
                                 <Paragraph>
                                    <Text strong>Default:</Text>{" "}
                                    {JSON.stringify(parameter.defaultValue)}
                                 </Paragraph>
                              )}
                           {parameter.description && (
                              <Paragraph>
                                 <Text strong>Description:</Text>{" "}
                                 {parameter.description}
                              </Paragraph>
                           )}
                        </div>
                     );

                     return (
                        <div
                           key={parameter.name}
                           style={{ marginBottom: "16px" }}
                        >
                           <div style={{ marginBottom: "4px" }}>
                              <Space>
                                 <span style={{ fontWeight: "500" }}>
                                    {parameter.name}
                                 </span>
                                 {parameter.required && (
                                    <Text type="danger">*</Text>
                                 )}
                                 <Popover
                                    content={helpContent}
                                    title="Parameter Info"
                                    trigger="hover"
                                 >
                                    <InfoCircleOutlined
                                       style={{
                                          color: "#1890ff",
                                          cursor: "help"
                                       }}
                                    />
                                 </Popover>
                              </Space>
                           </div>
                           {renderParameterInput(
                              parameter,
                              (nextValue: unknown) =>
                                 handleValueChange(parameter.name!, nextValue),
                              parameterValues[parameter.name!]
                           )}
                        </div>
                     );
                  })}
               </div>
            </Card>
         ) : (
            <div>
               <Alert
                  title="JSON Editor Mode"
                  description="Edit the parameters directly as JSON. Switch back to Form Builder for guided input."
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
               />
               <TextArea
                  value={jsonValue}
                  onChange={(event) => handleJsonChange(event.target.value)}
                  placeholder='{"key": "value"}'
                  rows={8}
                  style={{ fontFamily: "monospace", borderRadius: 8 }}
                  disabled={disabled}
               />
            </div>
         )}
      </div>
   );
};

export default JobParameterConfigurator;
