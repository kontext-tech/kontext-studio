import { InfoCircleOutlined } from "@kontext-tech/icons";
import { Input, Select, Space, Typography } from "antd";
import cronstrue from "cronstrue";
import React, { useCallback, useEffect, useState } from "react";

const { Text } = Typography;

interface CronBuilderProps {
   value?: string;
   onChange?: (value: string) => void;
}

const DEFAULT_CRON = "0 0 * * *";

interface CronParts {
   minute: string;
   hour: string;
   dayOfMonth: string;
   month: string;
   dayOfWeek: string;
}

const CronBuilder: React.FC<CronBuilderProps> = ({ value, onChange }) => {
   const [mode, setMode] = useState<"simple" | "advanced">("simple");
   const [cronExpression, setCronExpression] = useState("");
   const [humanReadable, setHumanReadable] = useState("");
   const [isValidCron, setIsValidCron] = useState(true);
   const [cronParts, setCronParts] = useState<CronParts>({
      minute: "0",
      hour: "0",
      dayOfMonth: "*",
      month: "*",
      dayOfWeek: "*"
   });
   const [frequency, setFrequency] = useState<
      "hourly" | "daily" | "weekly" | "monthly"
   >("daily");
   const [isUpdating, setIsUpdating] = useState(false);
   const [isInitialized, setIsInitialized] = useState(false);

   const validateCron = useCallback((cron: string): boolean => {
      if (!cron) return false;

      try {
         cronstrue.toString(cron);
         return true;
      } catch {
         return false;
      }
   }, []);

   const generateCronFromParts = useCallback((): string => {
      const { minute, hour, dayOfMonth, dayOfWeek } = cronParts;

      switch (frequency) {
         case "hourly":
            return `${minute} * * * *`;
         case "daily":
            return `${minute} ${hour} * * *`;
         case "weekly":
            return `${minute} ${hour} * * ${dayOfWeek}`;
         case "monthly":
            return `${minute} ${hour} ${dayOfMonth} * *`;
         default:
            return DEFAULT_CRON;
      }
   }, [cronParts, frequency]);

   const updateCron = useCallback(
      (cron: string, notifyParent = true) => {
         setCronExpression(cron);

         const isValid = validateCron(cron);
         setIsValidCron(isValid);

         try {
            setHumanReadable(
               isValid ? cronstrue.toString(cron) : "Invalid CRON expression"
            );
         } catch {
            setHumanReadable("Invalid CRON expression");
         }

         if (notifyParent && onChange && isValid) {
            onChange(cron);
         }
      },
      [onChange, validateCron]
   );

   const parseCron = useCallback(
      (cron: string) => {
         if (!cron || isUpdating) {
            return;
         }

         setIsUpdating(true);

         try {
            if (!validateCron(cron)) {
               setMode("advanced");
               setIsUpdating(false);
               return;
            }

            const parts = cron.split(" ");
            if (parts.length !== 5) {
               setMode("advanced");
               setIsUpdating(false);
               return;
            }

            const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

            if (
               minute.includes("/") ||
               minute.includes(",") ||
               minute.includes("-") ||
               hour.includes("/") ||
               hour.includes(",") ||
               hour.includes("-") ||
               dayOfMonth.includes("/") ||
               dayOfMonth.includes(",") ||
               dayOfMonth.includes("-") ||
               month !== "*" ||
               (dayOfWeek !== "*" &&
                  (dayOfWeek.includes("/") ||
                     dayOfWeek.includes(",") ||
                     dayOfWeek.includes("-")))
            ) {
               setMode("advanced");
               setIsUpdating(false);
               return;
            }

            const nextParts = {
               minute: minute !== "*" ? minute : "0",
               hour: hour !== "*" ? hour : "0",
               dayOfMonth,
               month,
               dayOfWeek
            };

            let nextFrequency: "hourly" | "daily" | "weekly" | "monthly";
            if (
               hour === "*" &&
               dayOfMonth === "*" &&
               month === "*" &&
               dayOfWeek === "*"
            ) {
               nextFrequency = "hourly";
            } else if (
               dayOfMonth === "*" &&
               month === "*" &&
               dayOfWeek === "*"
            ) {
               nextFrequency = "daily";
            } else if (
               dayOfMonth === "*" &&
               month === "*" &&
               dayOfWeek !== "*"
            ) {
               nextFrequency = "weekly";
            } else if (
               dayOfMonth !== "*" &&
               month === "*" &&
               dayOfWeek === "*"
            ) {
               nextFrequency = "monthly";
            } else {
               nextFrequency = "daily";
            }

            setCronParts(nextParts);
            setFrequency(nextFrequency);
            setMode("simple");

            setTimeout(() => {
               setIsUpdating(false);
            }, 0);
         } catch {
            setMode("advanced");
            setIsUpdating(false);
         }
      },
      [isUpdating, validateCron]
   );

   const updateFrequency = useCallback(
      (nextFrequency: "hourly" | "daily" | "weekly" | "monthly") => {
         setFrequency(nextFrequency);

         if (nextFrequency === "hourly") {
            setCronParts((prev) => ({ ...prev, hour: "*" }));
         } else if (nextFrequency === "daily") {
            setCronParts((prev) => ({
               ...prev,
               dayOfWeek: "*",
               dayOfMonth: "*"
            }));
         } else if (nextFrequency === "weekly") {
            setCronParts((prev) => ({
               ...prev,
               dayOfMonth: "*",
               dayOfWeek: prev.dayOfWeek === "*" ? "1" : prev.dayOfWeek
            }));
         } else if (nextFrequency === "monthly") {
            setCronParts((prev) => ({
               ...prev,
               dayOfWeek: "*",
               dayOfMonth: prev.dayOfMonth === "*" ? "1" : prev.dayOfMonth
            }));
         }
      },
      []
   );

   useEffect(() => {
      if (isUpdating) return;

      const effectiveValue =
         value === undefined || value === null || value === ""
            ? DEFAULT_CRON
            : value;

      if (effectiveValue !== cronExpression) {
         // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional prop-to-state sync for controlled component
         setCronExpression(effectiveValue);
         parseCron(effectiveValue);

         if (validateCron(effectiveValue)) {
            setHumanReadable(cronstrue.toString(effectiveValue));
            setIsValidCron(true);
         } else {
            setHumanReadable("Invalid CRON expression");
            setIsValidCron(false);
         }
      }

      if (!isInitialized) {
         setIsInitialized(true);
      }
   }, [
      value,
      cronExpression,
      parseCron,
      validateCron,
      isUpdating,
      isInitialized
   ]);

   useEffect(() => {
      if (isUpdating || !isInitialized) return;

      if (mode === "simple") {
         const nextCron = generateCronFromParts();
         if (nextCron !== cronExpression && nextCron !== value) {
            // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional parts-to-cron sync in simple mode
            updateCron(nextCron, true);
         }
      }
   }, [
      cronParts,
      frequency,
      mode,
      cronExpression,
      value,
      generateCronFromParts,
      updateCron,
      isUpdating,
      isInitialized
   ]);

   const hoursOptions = Array.from({ length: 24 }, (_, index) =>
      String(index).padStart(2, "0")
   );
   const minutesOptions = Array.from({ length: 60 }, (_, index) =>
      String(index).padStart(2, "0")
   );
   const daysOfMonthOptions = [
      "*",
      ...Array.from({ length: 31 }, (_, index) => String(index + 1))
   ];
   const daysOfWeekOptions = [
      { label: "Any", value: "*" },
      { label: "Sunday", value: "0" },
      { label: "Monday", value: "1" },
      { label: "Tuesday", value: "2" },
      { label: "Wednesday", value: "3" },
      { label: "Thursday", value: "4" },
      { label: "Friday", value: "5" },
      { label: "Saturday", value: "6" }
   ];

   return (
      <Space orientation="vertical" style={{ width: "100%" }}>
         <Select
            value={mode}
            onChange={setMode}
            style={{ width: 120 }}
            options={[
               { label: "Simple", value: "simple" },
               { label: "Advanced", value: "advanced" }
            ]}
         />

         {mode === "simple" && (
            <Space wrap align="end">
               <Space orientation="vertical" style={{ gap: 0 }}>
                  <Text>Frequency</Text>
                  <Select
                     value={frequency}
                     onChange={updateFrequency}
                     options={[
                        { label: "Hourly", value: "hourly" },
                        { label: "Daily", value: "daily" },
                        { label: "Weekly", value: "weekly" },
                        { label: "Monthly", value: "monthly" }
                     ]}
                     style={{ minWidth: 100 }}
                  />
               </Space>

               {frequency !== "hourly" && (
                  <Space orientation="vertical" style={{ gap: 0 }}>
                     <Text>Hour</Text>
                     <Select
                        value={cronParts.hour}
                        onChange={(hour) =>
                           setCronParts((prev) => ({ ...prev, hour }))
                        }
                        style={{ width: 80 }}
                        options={hoursOptions.map((hour) => ({
                           label: hour,
                           value: hour
                        }))}
                     />
                  </Space>
               )}

               <Space orientation="vertical" style={{ gap: 0 }}>
                  <Text>Minute</Text>
                  <Select
                     value={cronParts.minute}
                     onChange={(minute) =>
                        setCronParts((prev) => ({ ...prev, minute }))
                     }
                     style={{ width: 80 }}
                     options={minutesOptions.map((minute) => ({
                        label: minute,
                        value: minute
                     }))}
                  />
               </Space>

               {frequency === "weekly" && (
                  <Space orientation="vertical" style={{ gap: 0 }}>
                     <Text>Day of Week</Text>
                     <Select
                        value={cronParts.dayOfWeek}
                        onChange={(dayOfWeek) =>
                           setCronParts((prev) => ({ ...prev, dayOfWeek }))
                        }
                        style={{ width: 120 }}
                        options={daysOfWeekOptions}
                     />
                  </Space>
               )}

               {frequency === "monthly" && (
                  <Space orientation="vertical" style={{ gap: 0 }}>
                     <Text>Day of Month</Text>
                     <Select
                        value={cronParts.dayOfMonth}
                        onChange={(dayOfMonth) =>
                           setCronParts((prev) => ({ ...prev, dayOfMonth }))
                        }
                        style={{ width: 80 }}
                        options={daysOfMonthOptions.map((dayOfMonth) => ({
                           label: dayOfMonth,
                           value: dayOfMonth
                        }))}
                     />
                  </Space>
               )}
            </Space>
         )}

         {mode === "advanced" && (
            <Input
               value={cronExpression}
               onChange={(event) => updateCron(event.target.value)}
               placeholder="Enter CRON expression (e.g., 0 0 * * *)"
               status={isValidCron ? "" : "error"}
            />
         )}

         <Text type="secondary" style={{ marginTop: 8 }}>
            {humanReadable || "Select options to see human-readable format"}
         </Text>
         <Text type="secondary" style={{ marginTop: 8 }}>
            <InfoCircleOutlined style={{ marginRight: 4 }} />
            Note: schedules are processed by the server in UTC. Define the CRON
            expression against UTC time.
         </Text>
      </Space>
   );
};

export default CronBuilder;
