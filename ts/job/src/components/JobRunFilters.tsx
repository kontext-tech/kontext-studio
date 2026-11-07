import { ReloadOutlined } from "@kontext-tech/icons";
import { JobRunStatus } from "@kontext-tech/schema";
import { Button, Col, DatePicker, Row, Select, Space } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import React from "react";
import type { JobRunFilters } from "../jobTypes";

const { RangePicker } = DatePicker;
const { Option } = Select;

interface JobRunFiltersProps {
   filters: JobRunFilters;
   loading: boolean;
   onFilterChange: (
      key: string,
      value: string | JobRunStatus | undefined
   ) => void;
   onDateRangeChange: (dates: [Dayjs | null, Dayjs | null] | null) => void;
   onRefresh: () => void;
   onClearFilters: () => void;
}

const JobRunFiltersComponent: React.FC<JobRunFiltersProps> = ({
   filters,
   loading,
   onFilterChange,
   onDateRangeChange,
   onRefresh,
   onClearFilters
}) => {
   return (
      <Row gutter={[16, 16]} align="middle" wrap>
         <Col xs={24} sm={12} md={8} lg={6} xl={6}>
            <Select
               placeholder="Status"
               value={filters.status}
               onChange={(value) => onFilterChange("status", value)}
               allowClear
               style={{ width: "100%" }}
            >
               <Option value={JobRunStatus.Queued}>Queued</Option>
               <Option value={JobRunStatus.Dispatched}>Dispatched</Option>
               <Option value={JobRunStatus.Running}>Running</Option>
               <Option value={JobRunStatus.Succeeded}>Succeeded</Option>
               <Option value={JobRunStatus.Failed}>Failed</Option>
               <Option value={JobRunStatus.Canceled}>Canceled</Option>
               <Option value={JobRunStatus.TimedOut}>Timed Out</Option>
               <Option value={JobRunStatus.DeadLettered}>Dead Lettered</Option>
            </Select>
         </Col>
         <Col xs={24} sm={12} md={8} lg={6} xl={6}>
            <RangePicker
               placeholder={["Start Date", "End Date"]}
               value={
                  filters.startDate && filters.endDate
                     ? [dayjs(filters.startDate), dayjs(filters.endDate)]
                     : null
               }
               onChange={onDateRangeChange}
               style={{ width: "100%" }}
               showTime
            />
         </Col>
         <Col xs={24} sm={24} md={8} lg={12} xl={12}>
            <Space wrap>
               <Button
                  icon={<ReloadOutlined />}
                  onClick={onRefresh}
                  loading={loading}
               >
                  Refresh
               </Button>
               <Button onClick={onClearFilters}>Clear Filters</Button>
            </Space>
         </Col>
      </Row>
   );
};

export default JobRunFiltersComponent;
