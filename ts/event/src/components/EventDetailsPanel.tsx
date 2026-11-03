import { formatDate } from "@kontext-labs/common";
import { ChannelType, type EventModel } from "@kontext-labs/schema";
import { Descriptions, Space, Typography } from "antd";
import React from "react";
import BotInfoTag from "./BotInfoTag";
import EventTypeDisplay from "./EventTypeDisplay";

const { Text, Paragraph } = Typography;

interface EventDetailsPanelProps {
   event: EventModel;
}

const EventDetailsPanel: React.FC<EventDetailsPanelProps> = ({ event }) => {
   const items = [
      {
         key: "id",
         label: "Event ID",
         children: <Text code>{event.id}</Text>
      },
      {
         key: "type",
         label: "Event Type",
         children: event.type ? (
            <EventTypeDisplay type={event.type} showIcon showAsTag />
         ) : (
            <Text type="secondary">Unknown</Text>
         )
      },
      {
         key: "channel",
         label: "Channel",
         children: (
            <Text strong>
               {event.channelType === ChannelType.Web
                  ? "Web"
                  : event.channelType === ChannelType.Api
                    ? "API"
                    : "Unknown"}
            </Text>
         )
      },
      {
         key: "dateCreated",
         label: "Date Created",
         children: <Text>{formatDate(event.dateCreated)}</Text>
      },
      {
         key: "botInfo",
         label: "User Type",
         children: (
            <BotInfoTag
               isBot={event.botInfo?.isBot || false}
               botType={event.botInfo?.botType}
               botName={event.botInfo?.botName}
            />
         )
      }
   ];

   if (event.title) {
      items.push({
         key: "title",
         label: "Title",
         children: <Text>{event.title}</Text>
      });
   }

   if (event.content) {
      items.push({
         key: "content",
         label: "Content",
         children: (
            <Paragraph
               ellipsis={{ rows: 3, expandable: true }}
               style={{ marginBottom: 0 }}
            >
               {event.content}
            </Paragraph>
         )
      });
   }

   if (event.ipAddress) {
      items.push({
         key: "ipAddress",
         label: "IP Address",
         children: <Text code>{event.ipAddress}</Text>
      });
   }

   if (event.path) {
      items.push({
         key: "path",
         label: "Path",
         children: <Text code>{event.path}</Text>
      });
   }

   if (event.userId) {
      items.push({
         key: "userId",
         label: "User ID",
         children: <Text code>{event.userId}</Text>
      });
   }

   if (event.projectId) {
      items.push({
         key: "projectId",
         label: "Project ID",
         children: <Text code>{event.projectId}</Text>
      });
   }

   if (event.contentId) {
      items.push({
         key: "contentId",
         label: "Content ID",
         children: <Text code>{event.contentId}</Text>
      });
   }

   return (
      <Space direction="vertical" style={{ width: "100%" }}>
         <Descriptions
            bordered
            size="small"
            column={{ xxl: 2, xl: 2, lg: 2, md: 1, sm: 1, xs: 1 }}
            items={items}
         />
      </Space>
   );
};

export default EventDetailsPanel;
