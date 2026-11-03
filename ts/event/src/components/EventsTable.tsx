import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import {
   formatFullDateTime,
   formatNumberWithCommas,
   formatTimeAgo
} from "@kontext-labs/common";
import { UserAvatarById } from "@kontext-labs/identity";
import { ExpandAltOutlined, ShrinkOutlined } from "@kontext-labs/icons";
import type { EventModel } from "@kontext-labs/schema";
import { Button, Card, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import React, { useState } from "react";
import BotInfoTag from "./BotInfoTag";
import EventDetailsPanel from "./EventDetailsPanel";
import EventTypeDisplay from "./EventTypeDisplay";

const { Text } = Typography;

interface EventsTableProps {
   events: EventModel[];
   loading?: boolean;
   pagination?: {
      current: number;
      pageSize: number;
      total: number;
      onChange: (page: number, size?: number) => void;
   };
}

interface TableState {
   expandAll: boolean;
   expandedRows: string[];
}

const EventsTable: React.FC<EventsTableProps> = ({
   events,
   loading = false,
   pagination
}) => {
   const [tableState, setTableState] = useState<TableState>({
      expandAll: false,
      expandedRows: []
   });

   const toggleExpandAll = () => {
      const newExpandAll = !tableState.expandAll;
      setTableState({
         expandAll: newExpandAll,
         expandedRows: newExpandAll
            ? (events.map((e) => e.id).filter(Boolean) as string[])
            : []
      });
   };

   const handleExpand = (expanded: boolean, record: EventModel) => {
      const recordId = record.id;
      if (!recordId) return;

      const newExpandedRows = expanded
         ? [...tableState.expandedRows, recordId]
         : tableState.expandedRows.filter((id) => id !== recordId);

      setTableState((prev) => ({
         ...prev,
         expandedRows: newExpandedRows
      }));
   };

   const columns: ColumnsType<EventModel> = [
      {
         title: "Date Created",
         dataIndex: "dateCreated",
         key: "dateCreated",
         render: (date: string) => (
            <Text type="secondary" title={formatFullDateTime(date)}>
               {formatTimeAgo(date)}
            </Text>
         ),
         width: 120
      },
      {
         title: "Event",
         key: "event",
         render: (_, record) => (
            <>
               {record.type && <EventTypeDisplay type={record.type} showIcon />}
            </>
         ),
         width: 160
      },
      {
         title: "User Type",
         key: "userType",
         render: (_, record) => (
            <BotInfoTag
               isBot={record.botInfo?.isBot || false}
               botType={record.botInfo?.botType}
               botName={record.botInfo?.botName}
            />
         ),
         width: 96
      },
      {
         title: "User",
         dataIndex: "userId",
         key: "userId",
         render: (userId: string | null) =>
            userId ? (
               <UserAvatarById userId={userId} />
            ) : (
               <Text type="secondary">—</Text>
            ),
         width: 80
      },
      {
         title: "Title",
         dataIndex: "title",
         key: "title",
         render: (title: string) => title || <Text type="secondary">—</Text>,
         ellipsis: true,
         width: 200
      },
      {
         title: "IP Address",
         dataIndex: "ipAddress",
         key: "ipAddress",
         render: (ip: string) =>
            ip ? <Text>{ip}</Text> : <Text type="secondary">—</Text>,
         width: 120
      }
   ];

   return (
      <Card
         title={
            <Space>
               <span>Events</span>
               {events.length > 0 && (
                  <Text type="secondary">
                     ({formatNumberWithCommas(events.length)} results)
                  </Text>
               )}
            </Space>
         }
         extra={
            events.length > 0 && (
               <Button
                  shape="round"
                  icon={
                     tableState.expandAll ? (
                        <ShrinkOutlined />
                     ) : (
                        <ExpandAltOutlined />
                     )
                  }
                  onClick={toggleExpandAll}
               >
                  {tableState.expandAll ? "Collapse All" : "Expand All"}
               </Button>
            )
         }
      >
         <Table
            columns={columns}
            dataSource={events}
            loading={loading}
            rowKey="id"
            expandable={{
               expandedRowRender: (record) => (
                  <EventDetailsPanel event={record} />
               ),
               expandedRowKeys: tableState.expandedRows,
               onExpand: handleExpand,
               expandRowByClick: false
            }}
            pagination={
               pagination
                  ? {
                       current: pagination.current,
                       pageSize: pagination.pageSize,
                       total: pagination.total,
                       showSizeChanger: true,
                       pageSizeOptions: PAGE_SIZE_OPTIONS,
                       showQuickJumper: true,
                       showTotal: (total, range) =>
                          `${range[0]}-${range[1]} of ${formatNumberWithCommas(total)} events`,
                       onChange: pagination.onChange,
                       onShowSizeChange: pagination.onChange
                    }
                  : false
            }
            scroll={{ x: 800 }}
         />
      </Card>
   );
};

export default EventsTable;
