import type { ApiErrorResult } from "@kontext-labs/common";
import { useUserStore } from "@kontext-labs/identity";
import type { QueryResponse } from "@kontext-labs/schema";
import { TriggerActorType } from "@kontext-labs/schema";
import { LoadingSpinner, useUiApp } from "@kontext-labs/ui";
import { Button, Empty, Splitter, Tabs, theme, Typography } from "antd";
import React, { lazy, Suspense, useCallback, useState } from "react";
import { useProjectQuerySessions } from "../hooks";
import QueryHistoryTab from "./QueryHistoryTab";
import QueryResultsView from "./QueryResultsView";
import { QuerySessionManager } from "./QuerySessionManager";

const { Text } = Typography;

const SqlEditor = lazy(() => import("./SqlEditor"));

export interface ProjectSqlWorkspacePanelProps {
   projectId: string;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

const ProjectSqlWorkspacePanel: React.FC<ProjectSqlWorkspacePanelProps> = ({
   projectId,
   errorHandler
}) => {
   const { token } = theme.useToken();
   const { message } = useUiApp();
   const [sqlQuery, setSqlQuery] = useState("");
   const [isExecutingQuery, setIsExecutingQuery] = useState(false);
   const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
   const [historyRefreshTrigger, setHistoryRefreshTrigger] = useState(0);

   const { executeQuery, effectiveSession, ensureSession } =
      useProjectQuerySessions(projectId, errorHandler);

   const currentUserId = useUserStore((state) => state.user?.id);
   const effectiveSessionId = effectiveSession?.id;

   const handleSqlChange = useCallback((value: string) => {
      setSqlQuery(value);
   }, []);

   const handleExecuteQuery = useCallback(async () => {
      if (!sqlQuery.trim()) {
         message.warning("Please enter a query");
         return;
      }

      setIsExecutingQuery(true);
      setQueryResult(null);

      try {
         const preparedSession = await ensureSession();
         if (!preparedSession?.id) {
            message.error("Unable to prepare a query session");
            return;
         }

         const triggeredBy = currentUserId
            ? { type: TriggerActorType.User, id: currentUserId }
            : undefined;

         const result = await executeQuery(
            preparedSession.id,
            sqlQuery,
            triggeredBy
         );

         if (!result) {
            message.error("Query execution failed - no response received");
            return;
         }

         setQueryResult(result);

         if (result.success) {
            message.success("Query executed successfully");
         }

         setHistoryRefreshTrigger((prev) => prev + 1);
      } catch (error) {
         console.error("Error executing query:", error);
      } finally {
         setIsExecutingQuery(false);
      }
   }, [currentUserId, ensureSession, executeQuery, message, sqlQuery]);

   return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
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
            <div
               style={{
                  display: "flex",
                  alignItems: "center",
                  gap: token.marginSM
               }}
            >
               <Text strong>Run SQL</Text>
               <QuerySessionManager projectId={projectId} />
            </div>
            <Button
               type="primary"
               onClick={handleExecuteQuery}
               disabled={!sqlQuery.trim() || isExecutingQuery}
               loading={isExecutingQuery}
            >
               Execute
            </Button>
         </div>

         <div style={{ flex: 1, minHeight: 0 }}>
            <Splitter orientation="vertical" style={{ height: "100%" }}>
               <Splitter.Panel
                  defaultSize="50%"
                  min="300"
                  style={{ display: "flex", flexDirection: "column" }}
               >
                  <div
                     style={{
                        height: "100%",
                        width: "100%",
                        display: "flex",
                        flexDirection: "column"
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
                           <SqlEditor
                              value={sqlQuery}
                              onChange={handleSqlChange}
                              placeholder="Enter your SQL query here..."
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
                     defaultActiveKey="results"
                     items={[
                        {
                           key: "results",
                           label: "Results",
                           children: (
                              <div
                                 style={{
                                    height: "100%",
                                    padding: token.paddingMD
                                 }}
                              >
                                 {isExecutingQuery ? (
                                    <LoadingSpinner
                                       size="large"
                                       style={{
                                          height: "100%",
                                          minHeight: 200
                                       }}
                                    />
                                 ) : queryResult ? (
                                    <QueryResultsView response={queryResult} />
                                 ) : (
                                    <Empty
                                       description={
                                          effectiveSessionId
                                             ? "Run a query to see results"
                                             : "Run a query to create or reuse a session"
                                       }
                                    />
                                 )}
                              </div>
                           )
                        },
                        {
                           key: "history",
                           label: "History",
                           children: effectiveSessionId ? (
                              <div style={{ height: "100%" }}>
                                 <QueryHistoryTab
                                    projectId={projectId}
                                    sessionId={effectiveSessionId}
                                    refreshTrigger={historyRefreshTrigger}
                                 />
                              </div>
                           ) : (
                              <Empty
                                 description="Run a query to start session history"
                                 style={{ color: token.colorTextSecondary }}
                              />
                           )
                        }
                     ]}
                     style={{ height: "100%" }}
                  />
               </Splitter.Panel>
            </Splitter>
         </div>
      </div>
   );
};

export default ProjectSqlWorkspacePanel;
