import { Col, Form, Input, InputNumber, Row } from "antd";

import type { ConfigFieldDefinition } from "./formConfig";

type ConnectionSettingsFieldsProps = {
   fields: ConfigFieldDefinition[];
   disabled: boolean;
};

const ConnectionSettingsFields = ({
   fields,
   disabled
}: ConnectionSettingsFieldsProps) => {
   if (fields.length === 0) {
      return null;
   }

   return (
      <Row gutter={[12, 0]}>
         {fields.map((field) => (
            <Col span={field.columnSpan ?? 12} key={field.name}>
               <Form.Item
                  label={field.label}
                  name={field.name}
                  style={{ marginBottom: 12 }}
                  rules={
                     field.required
                        ? [
                             {
                                required: true,
                                message: `${field.label} is required`
                             }
                          ]
                        : undefined
                  }
               >
                  {field.type === "number" ? (
                     <InputNumber
                        style={{ width: "100%" }}
                        placeholder={field.placeholder}
                        disabled={disabled}
                     />
                  ) : (
                     <Input
                        type={field.type === "password" ? "password" : "text"}
                        placeholder={field.placeholder}
                        disabled={disabled}
                     />
                  )}
               </Form.Item>
            </Col>
         ))}
      </Row>
   );
};

export default ConnectionSettingsFields;
