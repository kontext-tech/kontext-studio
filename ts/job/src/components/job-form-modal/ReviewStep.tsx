import { Card, Descriptions, Form, Grid, Switch, Typography } from "antd";
import React from "react";
import type { StepProps } from "./modalTypes";

const { Title, Text } = Typography;
const { useBreakpoint } = Grid;

const ReviewStep: React.FC<StepProps> = ({
   form,
   selectedJobType,
   scheduleMode,
   parametersValue,
   isVisible
}) => {
   const screens = useBreakpoint();

   return (
      <div style={{ display: isVisible ? "block" : "none" }}>
         <Title level={screens.xs ? 5 : 4}>Review Job Configuration</Title>
         <Text type="secondary">
            Please review your job configuration before creating
         </Text>

         <Card title="Job Summary" style={{ marginTop: 24 }} size="small">
            <Descriptions
               column={screens.xs ? 1 : 2}
               size="small"
               layout={screens.xs ? "vertical" : "horizontal"}
               styles={{ label: { fontWeight: 600 } }}
            >
               <Descriptions.Item label="Job Name">
                  {form.getFieldValue("name") || (
                     <Text type="secondary">Not set</Text>
                  )}
               </Descriptions.Item>
               <Descriptions.Item label="Job Type">
                  {selectedJobType?.name || form.getFieldValue("type") || (
                     <Text type="secondary">Not selected</Text>
                  )}
               </Descriptions.Item>
               <Descriptions.Item label="Description">
                  {form.getFieldValue("description") || (
                     <Text type="secondary">No description</Text>
                  )}
               </Descriptions.Item>
               <Descriptions.Item label="Project ID">
                  {form.getFieldValue("projectId") || (
                     <Text type="secondary">System job</Text>
                  )}
               </Descriptions.Item>
               <Descriptions.Item label="Schedule">
                  {scheduleMode === "manual" ||
                  !form.getFieldValue("schedule") ? (
                     <Text type="secondary">Manual execution only</Text>
                  ) : (
                     form.getFieldValue("schedule")
                  )}
               </Descriptions.Item>
               {selectedJobType?.parameters &&
                  selectedJobType.parameters.length > 0 && (
                     <Descriptions.Item label="Parameters">
                        {parametersValue ? (
                           <Text type="success">Configured</Text>
                        ) : (
                           <Text type="secondary">Not configured</Text>
                        )}
                     </Descriptions.Item>
                  )}
            </Descriptions>

            {parametersValue && (
               <div style={{ marginTop: 16 }}>
                  <Text strong>Parameter Details:</Text>
                  <Card
                     size="small"
                     style={{ marginTop: 8, fontFamily: "monospace" }}
                  >
                     <pre
                        style={{
                           margin: 0,
                           fontSize: screens.xs ? "10px" : "12px",
                           whiteSpace: "pre-wrap",
                           wordBreak: "break-word"
                        }}
                     >
                        {parametersValue}
                     </pre>
                  </Card>
               </div>
            )}
         </Card>

         <Form.Item
            name="isEnabled"
            label="Enable Job"
            valuePropName="checked"
            style={{ marginTop: 24 }}
         >
            <Switch />
         </Form.Item>
      </div>
   );
};

export default ReviewStep;
