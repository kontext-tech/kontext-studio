import {
   getReadinessDescription,
   getReadinessStatusFor
} from "@/features/projects/components/data-sources/presentation";
import { useCatalogScope } from "@/features/chat/hooks/useCatalogScope";
import { TagOutlined } from "@kontext-tech/icons";
import { LoadingSpinner } from "@kontext-tech/ui";
import {
   Button,
   Card,
   Flex,
   Modal,
   Select,
   Space,
   Tabs,
   Tag,
   theme as antdTheme,
   Typography
} from "antd";
const { useToken } = antdTheme;
import { useMemo, useState } from "react";

const CATALOG_PROVIDER_LABELS: Record<string, string> = {
   iceberg_internal: "Internal Iceberg",
   duckdb_external: "DuckDB",
   mysql_external: "MySQL",
   oracle_external: "Oracle",
   postgresql_external: "PostgreSQL",
   sqlserver_external: "SQL Server",
   teradata_external: "Teradata",
   sqlite_external: "SQLite"
};

const getCatalogProviderLabel = (providerKind?: string) =>
   CATALOG_PROVIDER_LABELS[providerKind ?? ""] || providerKind || "Data Source";

interface SelectableCardProps {
   title: string;
   subtitle?: string;
   description?: string;
   selected: boolean;
   disabled?: boolean;
   onClick: () => void;
   badge?: React.ReactNode;
   action?: React.ReactNode;
}

const SelectableCard = ({
   title,
   subtitle,
   description,
   selected,
   disabled = false,
   onClick,
   badge,
   action
}: SelectableCardProps) => {
   const { token } = useToken();

   return (
      <Card
         size="small"
         hoverable
         style={{
            minWidth: 220,
            maxWidth: 280,
            cursor: disabled ? "not-allowed" : "pointer",
            borderColor: selected ? token.colorPrimary : token.colorBorder,
            boxShadow: selected ? token.boxShadowSecondary : "none",
            opacity: disabled ? 0.6 : 1
         }}
         onClick={disabled ? undefined : onClick}
         styles={{ body: { padding: 14 } }}
      >
         <Flex vertical gap={10}>
            <Flex justify="space-between" align="flex-start" gap="small">
               <Flex vertical gap={4} style={{ minWidth: 0 }}>
                  <Typography.Text strong ellipsis>
                     {title}
                  </Typography.Text>
                  {subtitle && (
                     <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {subtitle}
                     </Typography.Text>
                  )}
               </Flex>
               {badge}
            </Flex>
            {description && (
               <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {description}
               </Typography.Text>
            )}
            {action && (
               <div onClick={(event) => event.stopPropagation()}>{action}</div>
            )}
         </Flex>
      </Card>
   );
};

interface ChatScopeCustomizationModalProps {
   open: boolean;
   onClose: () => void;
   isPinTableOpen: boolean;
   setIsPinTableOpen: (open: boolean) => void;
   scopeSummary: string;
   scope: ReturnType<typeof useCatalogScope>;
}

/**
 * The "Choose Connected Source" modal behind the context scope button on the
 * new-chat page.
 */
export const ChatScopeCustomizationModal = ({
   open,
   onClose,
   isPinTableOpen,
   setIsPinTableOpen,
   scopeSummary,
   scope
}: ChatScopeCustomizationModalProps) => {
   const [activeCatalogProvider, setActiveCatalogProvider] = useState<string>();
   const {
      connections,
      namespaces,
      entities,
      selectedConnectionId,
      selectedNamespace,
      selectedEntityId,
      selectedConnection,
      isEntitiesLoading,
      hasLoadedEntities,
      loadEntities,
      clearEntitySelection,
      selectConnection,
      selectNamespace,
      selectEntity
   } = scope;
   const configuredNamespace = selectedConnection?.config?.defaultNamespace;

   const catalogProviderTabs = useMemo(
      () =>
         Array.from(
            new Set(connections.map((connection) => connection.providerKind))
         )
            .filter(Boolean)
            .map((providerKind) => ({
               key: providerKind,
               label: getCatalogProviderLabel(providerKind)
            })),
      [connections]
   );
   const effectiveCatalogProvider =
      activeCatalogProvider ||
      selectedConnection?.providerKind ||
      catalogProviderTabs[0]?.key;
   const visibleConnections = useMemo(
      () =>
         connections.filter(
            (connection) => connection.providerKind === effectiveCatalogProvider
         ),
      [connections, effectiveCatalogProvider]
   );
   const namespaceOptions = useMemo(
      () =>
         namespaces.map((namespace) => ({
            label: namespace.displayName || namespace.name,
            value: namespace.name,
            description:
               namespace.entityCount > 0
                  ? `${namespace.entityCount} table${
                       namespace.entityCount === 1 ? "" : "s"
                    }`
                  : "Namespace"
         })),
      [namespaces]
   );

   return (
      <Modal
         title="Choose Connected Source"
         open={open}
         onCancel={onClose}
         footer={
            <Button type="primary" onClick={onClose}>
               Done
            </Button>
         }
      >
         <Space orientation="vertical" size="large" style={{ width: "100%" }}>
            <div>
               <Typography.Text strong>Connected Source</Typography.Text>
               <Typography.Paragraph
                  type="secondary"
                  style={{ marginBottom: 0 }}
               >
                  Pick a connected source for this chat, then optionally narrow
                  it to a schema or table.
               </Typography.Paragraph>
            </div>

            {catalogProviderTabs.length > 0 && (
               <div>
                  <Tabs
                     activeKey={effectiveCatalogProvider}
                     onChange={setActiveCatalogProvider}
                     items={catalogProviderTabs}
                  />
                  <div
                     style={{
                        display: "flex",
                        gap: 12,
                        overflowX: "auto",
                        paddingBottom: 4
                     }}
                  >
                     {visibleConnections.map((connection) => {
                        const isSelected =
                           selectedConnectionId === connection.id;
                        const readiness = getReadinessStatusFor(
                           connection.readinessReason,
                           connection.isQueryReady,
                           { distinguishQueued: true }
                        );

                        return (
                           <SelectableCard
                              key={connection.id}
                              title={connection.displayName}
                              subtitle={
                                 connection.description ||
                                 getCatalogProviderLabel(
                                    connection.providerKind
                                 )
                              }
                              description={
                                 isSelected && scopeSummary
                                    ? `Current scope: ${scopeSummary}`
                                    : getReadinessDescription(connection)
                              }
                              selected={isSelected}
                              disabled={!connection.isQueryReady}
                              badge={
                                 <Tag color={readiness.color}>
                                    {readiness.label}
                                 </Tag>
                              }
                              onClick={() => {
                                 if (connection.id && connection.isQueryReady) {
                                    void selectConnection(connection.id);
                                    setIsPinTableOpen(false);
                                 }
                              }}
                           />
                        );
                     })}
                  </div>
               </div>
            )}

            <div>
               <Flex
                  justify="space-between"
                  align="center"
                  wrap
                  gap="small"
                  style={{ marginBottom: 8 }}
               >
                  <div>
                     <Typography.Text strong>
                        Namespace Override
                     </Typography.Text>
                     <Typography.Paragraph
                        type="secondary"
                        style={{ marginBottom: 0 }}
                     >
                        Optional. Leave blank to chat across the selected data
                        source.
                     </Typography.Paragraph>
                  </div>
                  {(selectedNamespace || configuredNamespace) && (
                     <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {selectedNamespace
                           ? "Custom namespace selected"
                           : `Configured default available: ${configuredNamespace}`}
                     </Typography.Text>
                  )}
               </Flex>

               <Select
                  allowClear
                  showSearch
                  size="large"
                  placeholder={
                     selectedConnection?.isQueryReady
                        ? "Choose a namespace"
                        : "Select a ready data source first"
                  }
                  value={selectedNamespace}
                  style={{ width: "100%" }}
                  optionFilterProp="label"
                  options={namespaceOptions}
                  optionRender={(option) => (
                     <div style={{ padding: "4px 0" }}>
                        <div style={{ fontWeight: 500 }}>
                           {option.data.label}
                        </div>
                        <div
                           style={{
                              fontSize: 12,
                              lineHeight: 1.4,
                              opacity: 0.7
                           }}
                        >
                           {String(option.data.description)}
                        </div>
                     </div>
                  )}
                  onChange={(value) => {
                     void selectNamespace(
                        typeof value === "string" ? value : undefined
                     );
                     setIsPinTableOpen(false);
                  }}
                  disabled={!selectedConnection?.isQueryReady}
               />
            </div>

            <div>
               <Flex
                  justify="space-between"
                  align="center"
                  wrap
                  gap="small"
                  style={{ marginBottom: 8 }}
               >
                  <div>
                     <Typography.Text strong>Table Override</Typography.Text>
                     <Typography.Paragraph
                        type="secondary"
                        style={{ marginBottom: 0 }}
                     >
                        Optional. Pin a single table only after choosing a
                        namespace.
                     </Typography.Paragraph>
                  </div>
                  <Space size="small">
                     {selectedEntityId && (
                        <Button type="link" onClick={clearEntitySelection}>
                           Clear pinned table
                        </Button>
                     )}
                     <Button
                        size="small"
                        icon={<TagOutlined />}
                        onClick={() => setIsPinTableOpen(!isPinTableOpen)}
                        disabled={
                           !selectedNamespace ||
                           !selectedConnection?.isQueryReady
                        }
                     >
                        {isPinTableOpen ? "Hide table pin" : "Pin a table"}
                     </Button>
                  </Space>
               </Flex>

               {isPinTableOpen && (
                  <Select
                     allowClear
                     showSearch
                     size="large"
                     placeholder={
                        isEntitiesLoading
                           ? "Loading tables..."
                           : "Select a table to pin"
                     }
                     value={selectedEntityId}
                     loading={isEntitiesLoading}
                     style={{ width: "100%" }}
                     optionFilterProp="label"
                     options={entities.map((entity) => ({
                        label: entity.displayName || entity.entityName,
                        value: entity.id,
                        description: `${entity.namespaceName}.${entity.entityName}`
                     }))}
                     optionRender={(option) => (
                        <div style={{ padding: "4px 0" }}>
                           <div style={{ fontWeight: 500 }}>
                              {option.data.label}
                           </div>
                           <div
                              style={{
                                 fontSize: 12,
                                 lineHeight: 1.4,
                                 opacity: 0.7
                              }}
                           >
                              {String(option.data.description)}
                           </div>
                        </div>
                     )}
                     notFoundContent={
                        isEntitiesLoading ? (
                           <LoadingSpinner />
                        ) : (
                           "No tables found in this namespace"
                        )
                     }
                     onDropdownVisibleChange={(visible) => {
                        if (
                           visible &&
                           selectedNamespace &&
                           !hasLoadedEntities &&
                           !isEntitiesLoading
                        ) {
                           void loadEntities();
                        }
                     }}
                     onChange={(value) =>
                        selectEntity(
                           typeof value === "string" ? value : undefined
                        )
                     }
                  />
               )}
            </div>
         </Space>
      </Modal>
   );
};
