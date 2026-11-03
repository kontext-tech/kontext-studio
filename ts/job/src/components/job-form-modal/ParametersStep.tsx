import { Card, Form, Grid, Typography } from "antd";
import React from "react";
import JobParameterConfigurator from "../JobParameterConfigurator";
import type { StepProps } from "./modalTypes";

const { Title, Text } = Typography;
const { useBreakpoint } = Grid;

const ParametersStep: React.FC<StepProps> = ({
   form,
   selectedJobType,
   parametersValue,
   setParametersValue,
   isVisible
}) => {
   const screens = useBreakpoint();

   const hasParameters =
      selectedJobType?.parameters && selectedJobType.parameters.length > 0;

   return (
      <div style={{ display: isVisible ? "block" : "none" }}>
         <Title level={screens.xs ? 5 : 4}>Job Parameters</Title>
         <Text type="secondary">
            {hasParameters
               ? `Configure parameters for your ${selectedJobType?.name || "job"}`
               : "This job type does not require any parameters."}
         </Text>

         {hasParameters ? (
            <Form.Item
               name="parameters"
               label="Parameters"
               help="Configure job parameters using the form builder or enter JSON directly."
               style={{ marginTop: 24 }}
            >
               <JobParameterConfigurator
                  parameters={selectedJobType.parameters || []}
                  value={parametersValue}
                  onChange={(value) => {
                     setParametersValue(value);
                     form.setFieldValue("parameters", value);
                  }}
               />
            </Form.Item>
         ) : (
            <Card style={{ marginTop: 16 }}>
               <Text>No parameters to configure for this job type.</Text>
            </Card>
         )}
      </div>
   );
};

export default ParametersStep;
