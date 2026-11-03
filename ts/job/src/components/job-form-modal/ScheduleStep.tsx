import { Alert, Button, Form, Grid, Space, Typography } from "antd";
import cronstrue from "cronstrue";
import React from "react";
import CronBuilder from "../CronBuilder";
import type { StepProps } from "./modalTypes";

const { Title, Text } = Typography;

const ScheduleStep: React.FC<StepProps> = ({
   form,
   editingJob,
   scheduleMode,
   setScheduleMode,
   isVisible
}) => {
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();
   const cronSchedule = Form.useWatch("schedule", form);

   const cronBuilderKey = React.useMemo(
      () => editingJob?.id || "new-job",
      [editingJob?.id]
   );

   const scheduleDescription = React.useMemo(() => {
      if (!cronSchedule || scheduleMode !== "scheduled") return null;

      try {
         return cronstrue.toString(cronSchedule);
      } catch {
         return null;
      }
   }, [cronSchedule, scheduleMode]);

   return (
      <div style={{ display: isVisible ? "block" : "none" }}>
         <Title level={screens.xs ? 5 : 4}>Job Schedule</Title>
         <Text type="secondary">
            Set up the execution schedule for your job.
         </Text>

         <Form.Item label="Execution Mode" style={{ marginTop: 24 }}>
            <Space.Compact style={{ width: screens.xs ? "100%" : "auto" }}>
               <Button
                  type={scheduleMode === "manual" ? "primary" : "default"}
                  style={{ flex: screens.xs ? 1 : "auto" }}
                  onClick={() => setScheduleMode("manual")}
               >
                  Manual
               </Button>
               <Button
                  type={scheduleMode === "scheduled" ? "primary" : "default"}
                  style={{ flex: screens.xs ? 1 : "auto" }}
                  onClick={() => setScheduleMode("scheduled")}
               >
                  Scheduled
               </Button>
            </Space.Compact>
         </Form.Item>

         {scheduleMode === "scheduled" && scheduleDescription && (
            <Alert
               message={`This job will run: ${scheduleDescription}`}
               type="info"
               showIcon
               style={{ marginTop: 16, marginBottom: 16 }}
            />
         )}

         {scheduleMode === "scheduled" && (
            <Form.Item
               name="schedule"
               label="Cron Schedule"
               style={{ marginTop: 16 }}
               rules={[
                  {
                     required: scheduleMode === "scheduled",
                     message: "Please enter a CRON schedule"
                  },
                  {
                     validator: (_, value) => {
                        if (scheduleMode !== "scheduled" || !value) {
                           return Promise.resolve();
                        }
                        try {
                           cronstrue.toString(value);
                           return Promise.resolve();
                        } catch {
                           return Promise.reject(
                              new Error("Invalid cron expression")
                           );
                        }
                     }
                  }
               ]}
            >
               <CronBuilder key={cronBuilderKey} />
            </Form.Item>
         )}
      </div>
   );
};

export default ScheduleStep;
