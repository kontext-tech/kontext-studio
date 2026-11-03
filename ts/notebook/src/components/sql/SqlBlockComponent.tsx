import {
   CodeOutlined,
   DatabaseOutlined,
   DownOutlined,
   LoadingOutlined,
   PlayCircleOutlined,
   UpOutlined
} from "@kontext-labs/icons";
import QueryResultsView from "@kontext-labs/query/query-results";
import type { SqlBlockData } from "@kontext-labs/schema";
import { CopyOutlined } from "@kontext-labs/icons";
import { LoadingSpinner } from "@kontext-labs/ui";
import type { BaseBlockConfig } from "@notebook/blocks/BaseReactBlock";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import {
   Alert,
   Button,
   Drawer,
   Input,
   Popover,
   Space,
   Splitter,
   Tabs,
   Tag,
   theme,
   Tooltip,
   Typography
} from "antd";
import React, { lazy, Suspense } from "react";
import { useNotebookServices } from "../../context/NotebookServiceContext";
import { useExecuteCell } from "../../hooks/useExecuteCell";
import {
   invalidateNotebookDataCache,
   useNotebookInlineData
} from "../../hooks/useInlineData";
import { useTheme } from "../../hooks/useTheme";
import { findSqlAliasError, sqlLoadDataSnippet } from "../../utils/sqlAlias";
import { resolveNotebookExecutionId } from "../../utils/notebookExecution";
import ExecutionRunLink from "../ExecutionRunLink";

// Lazy load SqlEditor for consistency with SqlWorkspacePanel
const LazySqlEditor = lazy(() => import("@kontext-labs/query/sql-editor"));

const { Text } = Typography;

type SqlInlineTable = NonNullable<SqlBlockData["inlineData"]>["table"];

function getSqlExecutionPayload(output: unknown): {
   dataRef?: { dataId?: string };
   inlineData?: SqlInlineTable;
   alias?: string;
} {
   if (!output || typeof output !== "object") {
      return {};
   }

   const candidate = output as {
      dataRef?: { dataId?: string };
      inlineData?: SqlInlineTable;
      result?: SqlInlineTable;
      alias?: string;
   };

   return {
      dataRef: candidate.dataRef,
      inlineData: candidate.inlineData ?? candidate.result,
      alias: candidate.alias || undefined
   };
}

interface SqlBlockComponentProps {
   data: SqlBlockData;
   config: BaseBlockConfig;
   onChange: (data: SqlBlockData) => void;
   readonly?: boolean;
   id: string;
}

export interface SqlBlockComponentRef {
   syncPendingChanges: () => void;
}

/**
 * Notebook-scope alias chip for SQL block results: shows the alias the
 * block's results are loadable by (`await kontext.load_data("df_1")`),
 * offers copy-to-clipboard of the exact snippet and a rename popover with
 * pattern/uniqueness validation. Renders nothing while no alias is bound
 * (Jupyter semantics: a name exists once the block saved results).
 */
const SqlAliasTag = ({
   alias,
   blockId,
   instanceId,
   readonly,
   onCommit
}: {
   alias: string | undefined;
   blockId: string;
   instanceId: string;
   readonly: boolean;
   onCommit: (alias: string | undefined) => void;
}) => {
   const { token } = theme.useToken();
   const [open, setOpen] = React.useState(false);
   const [draft, setDraft] = React.useState(alias ?? "");
   const [error, setError] = React.useState<string | null>(null);

   if (!alias) {
      return null;
   }

   const commit = () => {
      const trimmed = draft.trim();
      if (!trimmed) {
         onCommit(undefined);
         setOpen(false);
         setError(null);
         return;
      }
      const documentBlocks =
         useNotebookStore.getState().instances[instanceId]?.document?.blocks ??
         [];
      const aliasError = findSqlAliasError(trimmed, documentBlocks, blockId);
      if (aliasError) {
         setError(aliasError);
         return;
      }
      onCommit(trimmed);
      setOpen(false);
      setError(null);
   };

   const copySnippet = async () => {
      try {
         await navigator.clipboard?.writeText(sqlLoadDataSnippet(alias));
      } catch {
         // Clipboard may be unavailable (permissions/jsdom); ignore silently.
      }
   };

   return (
      <Space.Compact>
         <Popover
            open={open}
            trigger={readonly ? [] : "click"}
            onOpenChange={(nextOpen) => {
               setOpen(nextOpen);
               if (nextOpen) {
                  setDraft(alias);
                  setError(null);
               }
            }}
            title="Block alias"
            content={
               <div
                  style={{
                     display: "flex",
                     flexDirection: "column",
                     gap: 6,
                     width: 260
                  }}
               >
                  <Input
                     size="small"
                     value={draft}
                     onChange={(event) => setDraft(event.target.value)}
                     onPressEnter={commit}
                     placeholder="df_1"
                     data-testid="sql-alias-input"
                  />
                  {error && (
                     <Typography.Text type="danger" style={{ fontSize: 12 }}>
                        {error}
                     </Typography.Text>
                  )}
                  <Button
                     size="small"
                     type="primary"
                     onClick={commit}
                     data-testid="sql-alias-save"
                  >
                     Save alias
                  </Button>
               </div>
            }
         >
            <Tag
               data-testid="sql-alias-tag"
               color="geekblue"
               style={{
                  fontFamily: token.fontFamilyCode,
                  cursor: readonly ? "default" : "pointer",
                  marginInlineEnd: 0
               }}
            >
               {alias}
            </Tag>
         </Popover>
         <Tooltip title={`Copy ${sqlLoadDataSnippet(alias)}`}>
            <Button
               type="text"
               size="small"
               icon={<CopyOutlined />}
               onClick={copySnippet}
               style={{ minWidth: 0 }}
               aria-label="Copy load_data snippet"
            />
         </Tooltip>
      </Space.Compact>
   );
};

export const SqlBlockComponent = React.forwardRef<
   SqlBlockComponentRef,
   SqlBlockComponentProps
>(({ data, config, onChange, readonly = false, id }, ref) => {
   const instanceId = config.instanceId;
   const { token } = theme.useToken();
   const { isDarkMode } = useTheme(instanceId);
   const { execute: executeCell } = useExecuteCell("sql");

   // Get project context from notebook services
   const { projectId: contextProjectId, notebookId: contextNotebookId } =
      useNotebookServices();

   // Use context values as primary, but allow config to override if present
   const projectId = config.projectId || contextProjectId;

   const sqlBlock = useNotebookStore((state) =>
      state.getSqlBlock(id, instanceId || "default")
   );
   const isExecuting = sqlBlock?.data?.isExecuting || false;

   // Prefer the real notebook/file ID from host bindings; fall back for demos.
   const notebookId = resolveNotebookExecutionId(contextNotebookId, instanceId);

   // Local state - only sync when needed
   const [localCode, setLocalCode] = React.useState(data.code || "");
   const [localTitle, setLocalTitle] = React.useState(
      data.title || "SQL Query"
   );
   const [showResults, setShowResults] = React.useState(
      data.showResults ?? true
   );

   // The block may not exist in the store yet (a freshly inserted block is
   // only written to the store on save), so keep a local fallback to make the
   // editor drawer usable before the notebook is saved.
   const [localEditorOpen, setLocalEditorOpen] = React.useState(false);
   const isEditorOpen = sqlBlock?.data?.isEditorOpen ?? localEditorOpen;

   const setEditorOpen = React.useCallback(
      (nextOpen: boolean) => {
         setLocalEditorOpen(nextOpen);
         useNotebookStore
            .getState()
            .updateSqlBlockRuntime(
               id,
               { isEditorOpen: nextOpen },
               instanceId || "default"
            );
      },
      [id, instanceId]
   );

   const handleOpenEditor = React.useCallback(() => {
      setEditorOpen(true);
   }, [setEditorOpen]);

   const handleCloseEditor = React.useCallback(() => {
      setEditorOpen(false);
   }, [setEditorOpen]);

   // Sync local state with external data changes
   React.useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         setLocalCode(data.code || "");
         setLocalTitle(data.title || "SQL Query");
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [data.code, data.title]);

   // Resource ID for query results (always stored as resource now)
   const dataId = sqlBlock?.data?.dataRef?.dataId || data.dataRef?.dataId;
   const inlineTable =
      sqlBlock?.data?.inlineData?.table || data.inlineData?.table;
   // Run id of the job run behind the displayed results (survives reloads).
   const executionRunId = sqlBlock?.data?.executionRunId || data.executionRunId;

   // Load data table from resource storage
   const {
      data: loadedTable,
      isLoading: isLoadingResults,
      error: loadError
   } = useNotebookInlineData(dataId);

   // Combine inline results and stored data table results
   const table = React.useMemo(() => {
      if (dataId && loadedTable) return loadedTable;
      return inlineTable || undefined;
   }, [dataId, loadedTable, inlineTable]);

   // Calculate row count from loaded result
   const rowCount = React.useMemo(() => {
      if (!table) return 0;
      return table.rows?.length ?? 0;
   }, [table]);

   // Helper to update both store and parent component
   const updateData = React.useCallback(
      (updates: Partial<SqlBlockData>) => {
         useNotebookStore
            .getState()
            .updateSqlBlock(id, updates, instanceId || "default");
         onChange?.({
            ...data,
            ...updates
         });
      },
      [id, onChange, data, instanceId]
   );

   // Persist code edits shortly after typing stops, so they reach the store and
   // mark the notebook dirty (typing only updates local state otherwise).
   const codeSyncTimeoutRef = React.useRef<number | null>(null);
   React.useEffect(
      () => () => {
         if (codeSyncTimeoutRef.current !== null) {
            window.clearTimeout(codeSyncTimeoutRef.current);
         }
      },
      []
   );

   const handleCodeChange = (newCode: string) => {
      setLocalCode(newCode);

      if (codeSyncTimeoutRef.current !== null) {
         window.clearTimeout(codeSyncTimeoutRef.current);
      }
      codeSyncTimeoutRef.current = window.setTimeout(() => {
         codeSyncTimeoutRef.current = null;
         updateData({ code: newCode });
      }, 400);
   };

   // Sync pending changes - only called when needed
   const syncPendingChanges = React.useCallback(() => {
      const hasChanges = localCode !== data.code || localTitle !== data.title;

      if (hasChanges) {
         updateData({
            code: localCode,
            title: localTitle
         });
      }
   }, [localCode, localTitle, data.code, data.title, updateData]);

   // Expose syncPendingChanges method to parent via ref
   React.useImperativeHandle(
      ref,
      () => ({
         syncPendingChanges
      }),
      [syncPendingChanges]
   );

   const handleExecuteQuery = async () => {
      if (!localCode.trim() || readonly || !projectId) {
         return;
      }

      // Sync code changes to store before execution
      if (localCode !== data.code) {
         useNotebookStore
            .getState()
            .updateSqlBlock(id, { code: localCode }, instanceId || "default");
      }

      // Set executing state
      useNotebookStore
         .getState()
         .updateSqlBlockRuntime(
            id,
            { isExecuting: true },
            instanceId || "default"
         );

      try {
         const result = await executeCell(localCode, {
            notebookId,
            blockId: id
         });

         if (result.status === "error") {
            throw new Error(result.error || "Unknown SQL execution error");
         }

         // Run id of the job run backing this execution; persisted with the
         // results below so the run stays reachable after reloads.
         const executedRunId = result.executionRunId ?? null;
         const payload = getSqlExecutionPayload(result.output);

         // Aliases are bound server-side (single numbering authority): the
         // query-execution seam binds df_N/renames for notebook SQL blocks and
         // returns the name on the response; the client only adopts it.
         const adoptedAlias =
            payload.alias ?? sqlBlock?.data?.alias ?? data.alias;

         // Results are always stored as resources now (no inline data)
         if (payload.dataRef?.dataId) {
            const resultUpdates: Partial<SqlBlockData> = {
               dataRef: { dataId: payload.dataRef.dataId },
               inlineData: undefined,
               lastExecuted: Date.now(),
               executionRunId: executedRunId ?? undefined,
               alias: adoptedAlias
            };

            // Update block with resource ID
            useNotebookStore
               .getState()
               .updateSqlBlock(id, resultUpdates, instanceId || "default");

            // Trigger onChange with updated data
            updateData({
               title: localTitle,
               code: localCode,
               ...resultUpdates
            });

            invalidateNotebookDataCache(payload.dataRef.dataId);
         } else if (payload.inlineData) {
            // Handle inline results (non-stored)
            const inlineUpdates: Partial<SqlBlockData> = {
               dataRef: undefined,
               inlineData: {
                  title: localTitle || "SQL Result",
                  table: payload.inlineData
               },
               lastExecuted: Date.now(),
               executionRunId: executedRunId ?? undefined
            };

            useNotebookStore
               .getState()
               .updateSqlBlock(id, inlineUpdates, instanceId || "default");

            updateData({
               title: localTitle,
               code: localCode,
               ...inlineUpdates
            });
         } else {
            // No results or empty result set
            useNotebookStore
               .getState()
               .clearSqlResult(id, instanceId || "default");
         }
      } catch (error) {
         useNotebookStore
            .getState()
            .clearSqlResult(id, instanceId || "default");
         const errorMessage =
            error instanceof Error ? error.message : "Unknown error occurred";
         config.message?.error(`SQL execution failed: ${errorMessage}`);
      } finally {
         useNotebookStore
            .getState()
            .updateSqlBlockRuntime(
               id,
               { isExecuting: false },
               instanceId || "default"
            );
      }
   };

   const isExecuteDisabled = !localCode.trim() || isExecuting || readonly;

   // Compact summary card content
   const SummaryCard = (
      <div
         className="sql-block__card"
         style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderBottom:
               (dataId || table) &&
               showResults &&
               !isLoadingResults &&
               !loadError &&
               table
                  ? `1px solid ${token.colorBorderSecondary}`
                  : "none",
            background: token.colorFillAlter,
            gap: 12
         }}
      >
         <div
            style={{
               display: "flex",
               alignItems: "center",
               gap: 4,
               flex: 1
            }}
         >
            <DatabaseOutlined style={{ marginRight: 4 }} />
            <span
               style={{
                  fontWeight: 600,
                  fontSize: "14px",
                  color: token.colorTextSecondary,
                  userSelect: "none"
               }}
            >
               SQL
            </span>
            <span
               style={{
                  color: token.colorTextQuaternary,
                  fontSize: "14px",
                  marginLeft: 0
               }}
            >
               /
            </span>
            <Input
               variant="borderless"
               placeholder="SQL Query Title"
               value={localTitle}
               onChange={(e) => {
                  const val = e.target.value;
                  setLocalTitle(val);
                  updateData({ title: val });
               }}
               style={{
                  fontWeight: 600,
                  fontSize: "14px",
                  padding: 0,
                  flex: localTitle ? "0 1 auto" : "1",
                  minWidth: 100,
                  maxWidth: 360
               }}
            />
            <SqlAliasTag
               alias={data.alias}
               blockId={id}
               instanceId={instanceId || "default"}
               readonly={readonly}
               onCommit={(nextAlias) => updateData({ alias: nextAlias })}
            />
            {dataId ? (
               isLoadingResults ? (
                  <Tag icon={<LoadingOutlined />} color="processing">
                     loading...
                  </Tag>
               ) : loadError ? (
                  <Tag color="warning">error loading</Tag>
               ) : (
                  <Tag color="default">{rowCount} rows</Tag>
               )
            ) : table ? (
               <Tag color="default">{rowCount} rows</Tag>
            ) : (
               <Tag>no result</Tag>
            )}
            {isExecuting && <Tag color="orange">running…</Tag>}
         </div>
         {!readonly && (
            <Space>
               <Tooltip title={isExecuting ? "Executing..." : "Run"}>
                  <Button
                     type="text"
                     size="small"
                     icon={
                        isExecuting ? (
                           <LoadingOutlined />
                        ) : (
                           <PlayCircleOutlined />
                        )
                     }
                     loading={isExecuting}
                     disabled={isExecuteDisabled}
                     onClick={handleExecuteQuery}
                     style={{ minWidth: 0 }}
                  />
               </Tooltip>
               <Tooltip title="Open in full editor">
                  <Button
                     type="text"
                     size="small"
                     icon={<CodeOutlined />}
                     aria-label="Open in full editor"
                     onClick={handleOpenEditor}
                     style={{ minWidth: 0 }}
                  />
               </Tooltip>
               <Tooltip title={showResults ? "Hide results" : "Show results"}>
                  <Button
                     type="text"
                     size="small"
                     icon={showResults ? <UpOutlined /> : <DownOutlined />}
                     onClick={() => {
                        const next = !showResults;
                        setShowResults(next);
                        updateData({ showResults: next });
                     }}
                     disabled={!dataId && !table}
                     style={{ minWidth: 0 }}
                  />
               </Tooltip>
            </Space>
         )}
      </div>
   );

   return (
      <div className="kontext-notebook-editor sql-block">
         <div
            style={{
               border: "1px solid var(--editor-border)",
               borderRadius: 8,
               overflow: "hidden",
               background: token.colorBgContainer
            }}
         >
            {SummaryCard}

            {(dataId || table) &&
               showResults &&
               !isLoadingResults &&
               !loadError &&
               table && (
                  <div
                     style={{
                        maxHeight: 500,
                        display: "flex",
                        flexDirection: "column",
                        overflow: "auto"
                     }}
                  >
                     <QueryResultsView
                        response={{
                           result: table,
                           success: true,
                           dataId: dataId
                        }}
                        loading={isExecuting}
                        compact={true}
                     />
                  </div>
               )}
         </div>

         {/* Drawer editor for full SQL authoring */}
         <Drawer
            title={
               <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <DatabaseOutlined />
                  <Text strong>{localTitle}</Text>
               </div>
            }
            open={isEditorOpen}
            onClose={handleCloseEditor}
            size="large"
            styles={{ body: { padding: 0 } }}
            destroyOnHidden
         >
            <div
               style={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column"
               }}
            >
               {/* Header Row */}
               <div
                  style={{
                     display: "flex",
                     alignItems: "center",
                     gap: token.marginSM,
                     padding: token.paddingSM,
                     borderBottom: `1px solid ${token.colorBorder}`,
                     backgroundColor: token.colorBgContainer,
                     flexWrap: "wrap",
                     justifyContent: "space-between"
                  }}
               >
                  <Button
                     type="primary"
                     onClick={handleExecuteQuery}
                     disabled={isExecuteDisabled}
                     loading={isExecuting}
                     icon={<PlayCircleOutlined />}
                  >
                     Execute
                  </Button>
                  {/* Reachable while authoring; the block card header stays
                     free of it. */}
                  <ExecutionRunLink executionRunId={executionRunId} />
               </div>

               {/* Main Workspace with Splitter */}
               <div style={{ flex: 1, minHeight: 0 }}>
                  <Splitter orientation="vertical" style={{ height: "100%" }}>
                     <Splitter.Panel
                        defaultSize="50%"
                        min="300"
                        style={{
                           display: "flex",
                           flexDirection: "column"
                        }}
                     >
                        <div
                           style={{
                              height: "100%",
                              width: "100%",
                              display: "flex",
                              flexDirection: "column"
                              // paddingTop: token.paddingMD
                           }}
                        >
                           <Suspense
                              fallback={
                                 <div
                                    style={{
                                       display: "flex",
                                       justifyContent: "center",
                                       alignItems: "center",
                                       height: "200px"
                                    }}
                                 >
                                    <Text>Loading SQL Editor...</Text>
                                 </div>
                              }
                           >
                              <div
                                 style={{
                                    flex: 1,
                                    minHeight: 0,
                                    height: "100%"
                                 }}
                              >
                                 <LazySqlEditor
                                    value={localCode}
                                    onChange={handleCodeChange}
                                    placeholder={
                                       readonly
                                          ? "No SQL query provided"
                                          : "Enter your SQL query here..."
                                    }
                                    readOnly={readonly}
                                    isDarkMode={isDarkMode}
                                    borderRadius={0}
                                    borderless={true}
                                    fillParentHeight={true}
                                 />
                              </div>
                           </Suspense>
                        </div>
                     </Splitter.Panel>

                     <Splitter.Panel
                        defaultSize="50%"
                        style={{ padding: token.padding }}
                     >
                        <Tabs
                           defaultActiveKey="output"
                           items={[
                              {
                                 key: "output",
                                 label: "Output",
                                 children:
                                    !dataId && !table ? (
                                       <Text
                                          type="secondary"
                                          style={{ padding: token.paddingMD }}
                                       >
                                          {isExecuting
                                             ? "Executing query..."
                                             : "No output. Run a query to see results here."}
                                       </Text>
                                    ) : isLoadingResults ? (
                                       <LoadingSpinner
                                          size="large"
                                          style={{
                                             minHeight: 200,
                                             padding: token.paddingMD
                                          }}
                                       />
                                    ) : loadError ? (
                                       <Alert
                                          type="error"
                                          showIcon
                                          banner
                                          title="Failed to Load Output"
                                          description={
                                             loadError.message ||
                                             "An error occurred while loading the query results"
                                          }
                                          style={{ margin: token.paddingMD }}
                                       />
                                    ) : table ? (
                                       <QueryResultsView
                                          response={{
                                             result: table,
                                             success: true,
                                             dataId: dataId
                                          }}
                                          loading={isExecuting}
                                       />
                                    ) : (
                                       <Alert
                                          type="info"
                                          showIcon
                                          banner
                                          title="No Data Available"
                                          description="The query executed successfully but returned no data."
                                          style={{ margin: token.paddingMD }}
                                       />
                                    )
                              }
                           ]}
                           style={{
                              flex: 1,
                              display: "flex",
                              flexDirection: "column"
                           }}
                           tabBarStyle={{
                              paddingLeft: token.paddingMD,
                              paddingRight: token.paddingMD
                           }}
                        />
                     </Splitter.Panel>
                  </Splitter>
               </div>
            </div>
         </Drawer>
      </div>
   );
});

SqlBlockComponent.displayName = "SqlBlockComponent";

/**
 * Lightweight preview component for SQL blocks
 */
export const SqlBlockPreview: React.FC<{
   data: SqlBlockData;
   instanceId?: string;
}> = ({ data, instanceId: _instanceId }) => {
   const { token } = theme.useToken();
   const dataId = data.dataRef?.dataId;
   const inlineTable = data.inlineData?.table;

   // Load data table from resource storage if available
   const {
      data: loadedTable,
      isLoading,
      error
   } = useNotebookInlineData(dataId);

   // Combine inline results and stored data table results
   const table = React.useMemo(() => {
      if (dataId && loadedTable) return loadedTable;
      return inlineTable || undefined;
   }, [dataId, loadedTable, inlineTable]);

   return (
      <div className="sql-block-preview" style={{ marginBottom: 16 }}>
         <div
            style={{
               display: "flex",
               alignItems: "center",
               gap: 4,
               marginBottom: 8,
               fontSize: "14px"
            }}
         >
            <span style={{ fontWeight: 600, color: token.colorTextSecondary }}>
               SQL
            </span>
            <span style={{ color: token.colorTextQuaternary }}>/</span>
            <span style={{ fontWeight: 600 }}>
               {data.title || "Untitled Query"}
            </span>
            {data.executionRunId && (
               <span
                  style={{
                     marginLeft: "auto",
                     display: "inline-flex"
                  }}
               >
                  <ExecutionRunLink executionRunId={data.executionRunId} />
               </span>
            )}
         </div>
         {table ? (
            <div
               style={{
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 8,
                  overflow: "hidden"
               }}
            >
               <QueryResultsView
                  response={{
                     result: table,
                     success: true,
                     dataId: dataId
                  }}
                  loading={isLoading}
               />
            </div>
         ) : isLoading ? (
            <div style={{ padding: 20, textAlign: "center" }}>
               <LoadingSpinner size="small" />
            </div>
         ) : error ? (
            <Alert
               type="error"
               showIcon
               title="Failed to load SQL results"
               description={error.message}
            />
         ) : (
            <div
               style={{
                  padding: "12px",
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 8,
                  background: token.colorFillAlter
               }}
            >
               <Text type="secondary">No results available in preview.</Text>
            </div>
         )}
      </div>
   );
};
