import {
   ClockCircleOutlined,
   FileTextOutlined,
   HistoryOutlined,
   RobotOutlined,
   TableOutlined
} from "@kontext-tech/icons";
import type { DescriptionsProps } from "antd";
import { Descriptions, Empty, Space, Typography, theme } from "antd";

const { Text, Paragraph } = Typography;

export interface ProvenanceInfoProps {
   /** Notebook file ID that generated or owns the artifact. */
   notebookId?: string | null;
   /** Query session ID that produced the underlying data. */
   querySessionId?: string | null;
   /** AI chat session ID that generated the artifact. */
   chatSessionId?: string | null;
   /** SQL statement behind the artifact's data, when known. */
   sql?: string | null;
   /** Creation timestamp of the persisted artifact. */
   createdAt?: string | number | Date | null;
   /** Total rows in the full result row store, when materialized. */
   rowCount?: number | null;
   /** Additional descriptor rows (e.g. chart author/version/tags). */
   extraItems?: DescriptionsProps["items"];
   /** Optional title for the descriptions block. */
   title?: string;
}

const toDisplayDate = (value: string | number | Date): string => {
   const date = value instanceof Date ? value : new Date(value);
   return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
};

const CopyableId: React.FC<{ label: string; value: string }> = ({
   label,
   value
}) => (
   <Space size="small">
      <Text type="secondary" style={{ fontSize: 12 }}>
         {label}
      </Text>
      <Text code copyable={{ text: value }}>
         {value}
      </Text>
   </Space>
);

/**
 * ProvenanceInfo - Renders generation provenance metadata for persisted
 * artifacts (charts and `.dt` data tables) so users can trace an artifact back
 * to the notebook, query session, or AI chat session that produced it.
 */
const ProvenanceInfo: React.FC<ProvenanceInfoProps> = ({
   notebookId,
   querySessionId,
   chatSessionId,
   sql,
   createdAt,
   rowCount,
   extraItems,
   title = "Generation Provenance"
}) => {
   const { token } = theme.useToken();

   const items: NonNullable<DescriptionsProps["items"]> = [
      ...(notebookId
         ? [
              {
                 key: "notebookId",
                 label: (
                    <Space size="small">
                       <FileTextOutlined />
                       Notebook
                    </Space>
                 ),
                 children: <CopyableId label="ID" value={notebookId} />
              }
           ]
         : []),
      ...(querySessionId
         ? [
              {
                 key: "querySessionId",
                 label: (
                    <Space size="small">
                       <TableOutlined />
                       Query Session
                    </Space>
                 ),
                 children: <CopyableId label="ID" value={querySessionId} />
              }
           ]
         : []),
      ...(chatSessionId
         ? [
              {
                 key: "chatSessionId",
                 label: (
                    <Space size="small">
                       <RobotOutlined />
                       AI Session
                    </Space>
                 ),
                 children: <CopyableId label="ID" value={chatSessionId} />
              }
           ]
         : []),
      ...(rowCount !== null && rowCount !== undefined
         ? [
              {
                 key: "rowCount",
                 label: (
                    <Space size="small">
                       <TableOutlined />
                       Rows
                    </Space>
                 ),
                 children: <Text>{rowCount.toLocaleString()}</Text>
              }
           ]
         : []),
      ...(createdAt
         ? [
              {
                 key: "createdAt",
                 label: (
                    <Space size="small">
                       <ClockCircleOutlined />
                       Generated
                    </Space>
                 ),
                 children: <Text>{toDisplayDate(createdAt)}</Text>
              }
           ]
         : []),
      ...(extraItems ?? [])
   ];

   const hasProvenance =
      items.length > 0 || (sql !== null && sql !== undefined && sql !== "");

   if (!hasProvenance) {
      return (
         <Empty description="No provenance metadata recorded for this artifact" />
      );
   }

   return (
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
         {items.length > 0 && (
            <Descriptions
               column={1}
               size="small"
               bordered
               title={title}
               items={items}
            />
         )}

         {sql !== null && sql !== undefined && sql !== "" && (
            <div>
               <Space align="center" style={{ marginBottom: token.marginXS }}>
                  <HistoryOutlined style={{ color: token.colorPrimary }} />
                  <Text strong>SQL</Text>
               </Space>
               <Paragraph
                  style={{
                     margin: 0,
                     padding: token.paddingSM,
                     background: token.colorFillTertiary,
                     borderRadius: token.borderRadiusSM,
                     fontFamily: "monospace",
                     whiteSpace: "pre-wrap",
                     wordBreak: "break-word"
                  }}
               >
                  {sql}
               </Paragraph>
            </div>
         )}
      </Space>
   );
};

export default ProvenanceInfo;
