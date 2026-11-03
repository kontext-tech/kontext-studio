import {
   CodeOutlined,
   ErrorOutlined,
   InfoCircleOutlined,
   PlayCircleOutlined
} from "@kontext-tech/icons";
import { Card, Col, Row, Statistic, Typography } from "antd";
import React from "react";
import type { JobRunStatistics as JobRunStatisticsType } from "../jobTypes";

const JobRunStatistics: React.FC<JobRunStatisticsType> = ({
   runningJobs,
   failedJobs,
   totalCount,
   totalJobCount
}) => {
   return (
      <div style={{ marginBottom: "24px" }}>
         <Typography.Title level={5} style={{ marginBottom: "16px" }}>
            Job Run Overview
         </Typography.Title>
         <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} md={6} lg={6} xl={6}>
               <Card>
                  <Statistic
                     title="Active Now"
                     value={runningJobs.length}
                     prefix={<PlayCircleOutlined />}
                     suffix="running"
                  />
               </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={6} xl={6}>
               <Card>
                  <Statistic
                     title="Recent Failures"
                     value={failedJobs.length}
                     prefix={<ErrorOutlined />}
                     suffix={failedJobs.length === 1 ? "failed" : "failed"}
                  />
               </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={6} xl={6}>
               <Card>
                  <Statistic
                     title="Total Jobs"
                     value={totalJobCount}
                     prefix={<CodeOutlined />}
                     suffix="jobs"
                  />
               </Card>
            </Col>
            <Col xs={24} sm={12} md={6} lg={6} xl={6}>
               <Card>
                  <Statistic
                     title="Total Job Runs"
                     value={totalCount}
                     prefix={<InfoCircleOutlined />}
                     suffix="runs"
                  />
               </Card>
            </Col>
         </Row>
      </div>
   );
};

export default JobRunStatistics;
