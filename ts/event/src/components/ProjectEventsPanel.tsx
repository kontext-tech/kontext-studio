import type { ApiErrorResult } from "@kontext-tech/common";
import { ReloadOutlined } from "@kontext-tech/icons";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import type { EventModel } from "@kontext-tech/schema";
import { Button, Select, Space } from "antd";
import React, { useCallback, useEffect, useState } from "react";
import { ProjectEventService } from "../ProjectEventService";
import EventsTable from "./EventsTable";

const DATE_RANGE_OPTIONS = [
   { value: 1, label: "Last 24 hours" },
   { value: 7, label: "Last 7 days" },
   { value: 30, label: "Last 30 days" },
   { value: 90, label: "Last 90 days" },
   { value: 365, label: "Last year" }
] as const;

export interface ProjectEventsPanelProps {
   projectId: string;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   onMessage?: (
      type: "success" | "error" | "warning" | "info",
      content: string
   ) => void;
}

export const ProjectEventsPanel: React.FC<ProjectEventsPanelProps> = ({
   projectId,
   errorHandler,
   onMessage
}) => {
   const [events, setEvents] = useState<EventModel[]>([]);
   const [loading, setLoading] = useState(false);
   const [currentPage, setCurrentPage] = useState(1);
   const [pageSize, setPageSize] = useState(20);
   const [totalCount, setTotalCount] = useState(0);
   const [daysLimit, setDaysLimit] = useState(30);

   const projectEventService = useDataService(
      ProjectEventService,
      errorHandler
   );

   const fetchEvents = useCallback(
      async (
         pageIndex: number = currentPage,
         size: number = pageSize,
         days: number = daysLimit
      ) => {
         setLoading(true);
         try {
            const result = await projectEventService.getProjectEvents(
               projectId,
               pageIndex,
               size,
               undefined,
               days
            );

            if (result.succeed && result.data) {
               setEvents(result.data.items || []);
               setTotalCount(result.data.totalCount || 0);
            } else {
               onMessage?.(
                  "error",
                  result.error?.title ||
                     "Unable to load project events. Please try refreshing the page."
               );
               setEvents([]);
               setTotalCount(0);
            }
         } catch (error) {
            console.error("Error fetching events:", error);
            onMessage?.(
               "error",
               "Unable to load project events. Please try refreshing the page."
            );
            setEvents([]);
            setTotalCount(0);
         } finally {
            setLoading(false);
         }
      },
      [
         currentPage,
         daysLimit,
         onMessage,
         pageSize,
         projectEventService,
         projectId
      ]
   );

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void fetchEvents(currentPage, pageSize, daysLimit);
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [currentPage, pageSize, daysLimit, fetchEvents]);

   const handleDaysLimitChange = (value: number) => {
      setDaysLimit(value);
      setCurrentPage(1);
   };

   const handlePageChange = (page: number, size?: number) => {
      const nextPageSize = size || pageSize;
      setCurrentPage(page);
      if (size && size !== pageSize) {
         setPageSize(nextPageSize);
      }
   };

   return (
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
         <Space>
            <Select
               placeholder="Select date range"
               value={daysLimit}
               onChange={handleDaysLimitChange}
               options={[...DATE_RANGE_OPTIONS]}
               style={{ width: 200 }}
            />
            <Button
               icon={<ReloadOutlined />}
               onClick={() => void fetchEvents()}
               loading={loading}
            >
               Refresh
            </Button>
         </Space>
         <EventsTable
            events={events}
            loading={loading}
            pagination={{
               current: currentPage,
               pageSize,
               total: totalCount,
               onChange: handlePageChange
            }}
         />
      </Space>
   );
};
