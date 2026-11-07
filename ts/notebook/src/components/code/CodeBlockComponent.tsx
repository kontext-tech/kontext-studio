import {
   CodeOutlined,
   DownOutlined,
   InfoCircleOutlined,
   PlayCircleOutlined,
   StopOutlined,
   UpOutlined
} from "@kontext-tech/icons";
import {
   type CodeBlockData,
   type CodeExecutionOutput,
   type PythonExecutionMode
} from "@kontext-tech/schema";
import { useTheme } from "@kontext-tech/theme";
import { LoadingSpinner } from "@kontext-tech/ui";
import type { BaseBlockConfig } from "@notebook/blocks/BaseReactBlock";
import ExecutionRunLink from "@notebook/components/ExecutionRunLink";
import LazyCodeEditor from "@notebook/components/code/LazyCodeEditor";
import { useNotebookServices } from "@notebook/context/NotebookServiceContext";
import { useExecuteCell } from "@notebook/hooks/useExecuteCell";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import {
   normalizeCodeBlockData,
   PYTHON_CODE_BLOCK_LABEL,
   PYTHON_CODE_BLOCK_LANGUAGE
} from "@notebook/utils/codeBlock";
import { resolveNotebookExecutionId } from "@notebook/utils/notebookExecution";
import { Button, Input, Space, Tag, theme, Tooltip } from "antd";
import React, { useCallback, useEffect, useMemo, useState } from "react";

export interface CodeBlockComponentProps {
   data: CodeBlockData;
   config: BaseBlockConfig;
   onChange: (data: CodeBlockData) => void;
   readonly?: boolean;
   id: string;
   previewMode?: boolean;
}

export interface CodeBlockComponentRef {
   syncPendingChanges: () => void;
}

const createTextOutput = (content: string): CodeExecutionOutput => ({
   type: "text",
   mimeType: "text/plain",
   content
});

/**
 * Shared component to render code execution outputs
 */
export const CodeBlockOutputs: React.FC<{
   outputs: CodeExecutionOutput[];
   style?: React.CSSProperties;
   isLoading?: boolean;
   executionRunId?: string | null;
   executionMode?: PythonExecutionMode | null;
   lastExecuted?: number | null;
}> = ({
   outputs,
   style,
   isLoading,
   executionRunId,
   executionMode,
   lastExecuted
}) => {
   const { token } = theme.useToken();
   const { isDarkMode } = useTheme();
   const { fileSystem, projectId } = useNotebookServices();
   const executionStatusTooltip = executionMode ? (
      <div>
         <div>
            {executionMode === "persisted"
               ? "Saved execution: outputs are part of the notebook state."
               : "Draft execution: outputs are transient and are not saved to the notebook file."}
         </div>
         {lastExecuted && (
            <div>Executed: {new Date(lastExecuted).toLocaleString()}</div>
         )}
         {executionRunId && <div>Execution run: {executionRunId}</div>}
      </div>
   ) : null;

   if (isLoading) {
      return (
         <div style={{ padding: 12, textAlign: "center", ...style }}>
            <LoadingSpinner size="medium" />
         </div>
      );
   }

   if (!outputs || outputs.length === 0) return null;

   return (
      <div
         className="code-block-outputs"
         style={{
            padding: "16px",
            marginTop: "0.15rem",
            backgroundColor: isDarkMode
               ? token.colorFillTertiary
               : token.colorBgLayout,
            borderRadius: "0 0 8px 8px",
            fontFamily:
               '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, monospace',
            fontSize: "13px",
            color: token.colorText,
            lineHeight: 1.5,
            ...style
         }}
      >
         <div
            style={{
               fontSize: "11px",
               textTransform: "uppercase",
               letterSpacing: "0.05em",
               color: token.colorTextSecondary,
               marginBottom: 12,
               fontWeight: 600,
               display: "flex",
               alignItems: "center",
               justifyContent: "space-between",
               gap: 8
            }}
         >
            <span>Output</span>
            <span
               style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8
               }}
            >
               <ExecutionRunLink executionRunId={executionRunId} />
               {executionStatusTooltip && (
                  <Tooltip title={executionStatusTooltip}>
                     <span
                        aria-label="Execution info"
                        style={{
                           display: "inline-flex",
                           alignItems: "center",
                           color: token.colorTextSecondary,
                           cursor: "help",
                           fontSize: 12
                        }}
                     >
                        <InfoCircleOutlined />
                     </span>
                  </Tooltip>
               )}
            </span>
         </div>
         {outputs.map((out, idx) => (
            <div
               key={idx}
               style={{
                  marginBottom: idx === outputs.length - 1 ? 0 : 16,
                  padding: out.type === "text" ? "4px 0" : 0
               }}
            >
               {out.type === "text" && (
                  <div
                     style={{
                        // Preserve stdout/stderr line breaks; wrap very long
                        // tokens (tracebacks, URLs) that cannot fit a line.
                        whiteSpace: "pre-wrap",
                        overflowWrap: "break-word"
                     }}
                  >
                     {out.content}
                  </div>
               )}
               {out.type === "image" && (
                  <div
                     style={{
                        textAlign: "center",
                        background: isDarkMode ? token.colorFillAlter : "#fff",
                        padding: 16,
                        borderRadius: token.borderRadius,
                        border: `1px solid ${token.colorBorderSecondary}`,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
                     }}
                  >
                     <img
                        src={`data:image/png;base64,${out.content}`}
                        alt="Execution plot"
                        style={{
                           maxWidth: "100%",
                           height: "auto",
                           filter: isDarkMode ? "none" : "none" // We can add filter if needed, but plots are usually fine
                        }}
                     />
                  </div>
               )}
               {out.type === "image_ref" && (
                  <ImageRefOutput
                     fileId={out.fileId}
                     imageUrl={out.imageUrl}
                     projectId={projectId}
                     fileSystem={fileSystem}
                     isDarkMode={isDarkMode}
                  />
               )}
               {out.type === "json" && (
                  <div
                     style={{
                        padding: 12,
                        background: token.colorFillAlter,
                        borderRadius: token.borderRadius,
                        border: `1px solid ${token.colorBorderSecondary}`
                     }}
                  >
                     <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                        {JSON.stringify(JSON.parse(out.content), null, 2)}
                     </pre>
                  </div>
               )}
            </div>
         ))}
      </div>
   );
};

const ImageRefOutput: React.FC<{
   fileId: string;
   imageUrl?: string;
   projectId?: string;
   fileSystem?: ReturnType<typeof useNotebookServices>["fileSystem"];
   isDarkMode: boolean;
}> = ({ fileId, imageUrl, projectId, fileSystem, isDarkMode }) => {
   const { token } = theme.useToken();
   const [url, setUrl] = useState<string | null>(imageUrl || null);
   const [error, setError] = useState<string | null>(null);
   const effectiveUrl = !fileId && imageUrl ? imageUrl : url;

   useEffect(() => {
      // If we have a fileId, always prefer downloading via the service to get a blob URL.
      // This ensures authorization headers are included and the image works reliably,
      // as direct URLs to the file service may require authentication.
      if (!fileId && imageUrl) {
         return;
      }

      let mounted = true;
      let objectUrl: string | null = null;

      const load = async () => {
         if (!projectId || !fileSystem?.downloadFile) {
            setError("Missing projectId for image download");
            return;
         }

         try {
            const result = await fileSystem.downloadFile(fileId, projectId);
            if (!result.succeed || !result.data?.blob) {
               throw new Error("Failed to download image");
            }
            objectUrl = URL.createObjectURL(result.data.blob);
            if (mounted) {
               setUrl(objectUrl);
            }
         } catch (e: unknown) {
            // Fallback to imageUrl if download fails and it exists
            if (mounted) {
               if (imageUrl) {
                  setUrl(imageUrl);
               } else {
                  setError(e instanceof Error ? e.message : String(e));
               }
            }
         }
      };

      load();

      return () => {
         mounted = false;
         if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
         }
      };
   }, [fileId, fileSystem, projectId, imageUrl]);

   if (error) {
      return (
         <pre
            style={{
               margin: 0,
               whiteSpace: "pre-wrap",
               color: token.colorError
            }}
         >
            {error}
         </pre>
      );
   }

   if (!effectiveUrl) {
      return (
         <div style={{ padding: 12, textAlign: "center" }}>Loading image…</div>
      );
   }

   return (
      <div
         style={{
            textAlign: "center",
            background: isDarkMode ? token.colorFillAlter : "#fff",
            padding: 16,
            borderRadius: token.borderRadius,
            border: `1px solid ${token.colorBorderSecondary}`,
            boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
         }}
      >
         <img
            src={effectiveUrl}
            alt="Execution plot"
            style={{
               maxWidth: "100%",
               height: "auto"
            }}
         />
      </div>
   );
};

export const CodeBlockComponent = React.forwardRef<
   CodeBlockComponentRef,
   CodeBlockComponentProps
>(
   (
      {
         data,
         config: _config,
         onChange,
         readonly = false,
         id,
         previewMode = false
      },
      ref
   ) => {
      const { token } = theme.useToken();
      const { isDarkMode } = useTheme();
      const { notebookId: contextNotebookId } = useNotebookServices();
      const normalizedData = useMemo(
         () => normalizeCodeBlockData(data),
         [data]
      );

      const [isExecuting, setIsExecuting] = useState(
         normalizedData.isExecuting || false
      );
      const [outputs, setOutputs] = useState<CodeExecutionOutput[]>(
         normalizedData.outputs || []
      );
      const [localTitle, setLocalTitle] = useState(normalizedData.title || "");
      const [localCode, setLocalCode] = useState(normalizedData.code || "");
      const [executionMode, setExecutionMode] = useState<
         "draft" | "persisted" | null
      >(null);
      const [executionRunId, setExecutionRunId] = useState<string | null>(
         normalizedData.executionRunId ?? null
      );
      const [cancelError, setCancelError] = useState<string | null>(null);
      const [lastExecuted, setLastExecuted] = useState<number | null>(
         normalizedData.lastExecuted ?? null
      );
      const [showCode, setShowCode] = useState(
         previewMode && (normalizedData.outputs?.length ?? 0) > 0
            ? false
            : normalizedData.showCode !== false
      );
      const { execute: executeCell, cancel: cancelCell } = useExecuteCell(
         PYTHON_CODE_BLOCK_LANGUAGE
      );

      const effectiveReadonly = readonly || isExecuting;
      const lastExecutedValue = lastExecuted ?? undefined;
      const hasTitle = localTitle.trim().length > 0;

      const buildCodeBlockData = useCallback(
         (nextData: Partial<CodeBlockData> = {}): CodeBlockData =>
            normalizeCodeBlockData({
               ...normalizedData,
               title: localTitle,
               code: localCode,
               showCode,
               outputs,
               isExecuting,
               lastExecuted: lastExecutedValue,
               executionRunId: executionRunId ?? undefined,
               ...nextData
            }),
         [
            normalizedData,
            localTitle,
            localCode,
            showCode,
            outputs,
            isExecuting,
            lastExecutedValue,
            executionRunId
         ]
      );

      // Subscribe to store updates for execution state (runtime source of truth)
      const storeBlock = useNotebookStore(
         useCallback(
            (state) => state.getCodeBlock(id, _config.instanceId || "default"),
            [id, _config.instanceId]
         )
      );

      // Effect to sync from store (Priority: Store > Local for runtime state)
      useEffect(() => {
         if (!storeBlock?.data) return;

         const storeData = storeBlock.data;

         // Sync execution state
         if (
            storeData.isExecuting !== undefined &&
            storeData.isExecuting !== isExecuting
         ) {
            window.setTimeout(() => {
               setIsExecuting(storeData.isExecuting ?? false);
            }, 0);
            // Also notify EditorJS model of the state change
            onChange(
               buildCodeBlockData({ isExecuting: storeData.isExecuting })
            );
         }

         if (
            storeData.lastExecuted !== undefined &&
            storeData.lastExecuted !== lastExecuted
         ) {
            window.setTimeout(() => {
               setLastExecuted(storeData.lastExecuted ?? null);
            }, 0);
         }

         if (
            storeData.executionRunId !== undefined &&
            storeData.executionRunId !== executionRunId
         ) {
            window.setTimeout(() => {
               setExecutionRunId(storeData.executionRunId ?? null);
            }, 0);
         }

         // Sync outputs (use stable comparison to avoid infinite loops)
         if (
            storeData.outputs !== undefined &&
            JSON.stringify(storeData.outputs) !== JSON.stringify(outputs)
         ) {
            window.setTimeout(() => {
               setOutputs(storeData.outputs ?? []);
            }, 0);
            // Also notify EditorJS model to persist outputs
            onChange(buildCodeBlockData({ outputs: storeData.outputs }));
         }
      }, [
         storeBlock,
         isExecuting,
         lastExecuted,
         executionRunId,
         outputs,
         onChange,
         buildCodeBlockData
      ]);

      // Source of Truth Synchronization:
      // We use render-phase state updates to sync from props (e.g. for Undo/Redo)
      // while maintaining local state for immediate responsiveness and buffering.
      // This is the pattern recommended by React (https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes)
      const [lastSeenData, setLastSeenData] = useState(normalizedData);

      if (normalizedData !== lastSeenData) {
         if (normalizedData.title !== lastSeenData.title)
            setLocalTitle(normalizedData.title || "");
         if (normalizedData.code !== lastSeenData.code)
            setLocalCode(normalizedData.code || "");
         if (normalizedData.outputs !== lastSeenData.outputs)
            setOutputs(normalizedData.outputs || []);
         if (normalizedData.isExecuting !== lastSeenData.isExecuting)
            setIsExecuting(normalizedData.isExecuting || false);
         if (normalizedData.lastExecuted !== lastSeenData.lastExecuted)
            setLastExecuted(normalizedData.lastExecuted || null);
         if (normalizedData.executionRunId !== lastSeenData.executionRunId)
            setExecutionRunId(normalizedData.executionRunId || null);
         if (normalizedData.showCode !== lastSeenData.showCode)
            setShowCode(normalizedData.showCode !== false);
         setLastSeenData(normalizedData);
      }

      // Synchronize ref for direct access from the block class if needed
      React.useImperativeHandle(ref, () => ({
         syncPendingChanges: () => {
            onChange(buildCodeBlockData());
         }
      }));

      const syncBlockState = useCallback(
         (nextData: Partial<CodeBlockData>) => {
            useNotebookStore
               .getState()
               .updateBlockData(id, nextData, _config.instanceId || "default");

            onChange(buildCodeBlockData(nextData));
         },
         [id, _config.instanceId, onChange, buildCodeBlockData]
      );

      const updateRuntimeState = useCallback(
         (nextData: Partial<CodeBlockData>) => {
            useNotebookStore
               .getState()
               .updateBlockData(id, nextData, _config.instanceId || "default", {
                  markDirty: false
               });
         },
         [id, _config.instanceId]
      );

      const handleRun = async () => {
         if (isExecuting) return;

         const notebookExecutionId = resolveNotebookExecutionId(
            contextNotebookId,
            _config.instanceId
         );

         syncBlockState({
            title: localTitle,
            code: localCode,
            showCode
         });

         setIsExecuting(true);
         setOutputs([]);
         setExecutionMode(null);
         setExecutionRunId(null);
         setCancelError(null);
         updateRuntimeState({ isExecuting: true, outputs: [] });

         // Job run id backing this execution; persisted with the outputs
         // below so the run stays reachable after reloads.
         let executedRunId: string | null = null;

         try {
            const result = await executeCell(localCode, {
               notebookId: notebookExecutionId,
               blockId: id
            });
            executedRunId = result.executionRunId ?? null;
            setExecutionMode(result.executionMode ?? null);
            setExecutionRunId(executedRunId);

            if (result.status === "error") {
               throw new Error(result.error || "Unknown execution error");
            }

            const nextOutputs = Array.isArray(result.output)
               ? (result.output as CodeExecutionOutput[])
               : [];
            const executedAt = Date.now();

            setOutputs(nextOutputs);
            setLastExecuted(executedAt);

            // Sync result to store immediately
            updateRuntimeState({
               outputs: nextOutputs,
               isExecuting: false,
               lastExecuted: executedAt,
               executionRunId: executedRunId ?? undefined
            });

            onChange(
               buildCodeBlockData({
                  outputs: nextOutputs,
                  isExecuting: false,
                  lastExecuted: executedAt,
                  executionRunId: executedRunId ?? undefined
               })
            );
         } catch (error: unknown) {
            const errorMsg =
               error instanceof Error ? error.message : String(error);
            const errorOutput: CodeExecutionOutput = {
               ...createTextOutput(errorMsg || "Unknown execution error")
            };
            const executedAt = Date.now();
            setOutputs([errorOutput]);
            setLastExecuted(executedAt);

            // Sync error to store immediately
            updateRuntimeState({
               outputs: [errorOutput],
               isExecuting: false,
               lastExecuted: executedAt,
               executionRunId: executedRunId ?? undefined
            });

            onChange(
               buildCodeBlockData({
                  outputs: [errorOutput],
                  isExecuting: false,
                  lastExecuted: executedAt,
                  executionRunId: executedRunId ?? undefined
               })
            );
         } finally {
            setIsExecuting(false);
         }
      };

      const toggleCode = () => {
         const newValue = !showCode;
         setShowCode(newValue);
         onChange(buildCodeBlockData({ showCode: newValue }));
      };

      const handleStop = async () => {
         const notebookExecutionId = resolveNotebookExecutionId(
            contextNotebookId,
            _config.instanceId
         );

         const cancelled = await cancelCell({
            notebookId: notebookExecutionId,
            blockId: id
         });

         if (!cancelled) {
            setCancelError(
               "Could not find an in-flight run for this cell to cancel."
            );
         } else {
            setCancelError(null);
         }
      };

      // In preview mode, if we have outputs, we ONLY show the outputs.
      // Otherwise we show the code (readonly).
      const SummaryCard = (
         <div
            className="code-block__card"
            style={{
               display: "flex",
               alignItems: "center",
               justifyContent: "space-between",
               flexWrap: "wrap",
               padding: "8px 12px",
               borderBottom:
                  showCode || outputs.length > 0
                     ? `1px solid ${token.colorBorderSecondary}`
                     : "none",
               background: token.colorFillAlter,
               gap: 12
            }}
         >
            <div
               className="code-block__header-left"
               style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flex: "1 1 240px",
                  minWidth: 0
               }}
            >
               <CodeOutlined style={{ flex: "0 0 auto" }} />
               <span
                  className="code-block__language-label"
                  style={{
                     fontWeight: 600,
                     fontSize: "14px",
                     color: token.colorTextSecondary,
                     userSelect: "none",
                     flex: "0 0 auto"
                  }}
               >
                  {PYTHON_CODE_BLOCK_LABEL}
               </span>
               {hasTitle && (
                  <span
                     className="code-block__title-separator"
                     style={{
                        color: token.colorTextQuaternary,
                        fontSize: "14px",
                        flex: "0 0 auto"
                     }}
                  >
                     /
                  </span>
               )}
               <Input
                  className="code-block__title-input"
                  variant="borderless"
                  placeholder=""
                  value={localTitle}
                  readOnly={effectiveReadonly}
                  aria-label="Code block title"
                  onChange={(e) => {
                     const val = e.target.value;
                     setLocalTitle(val);
                     onChange(buildCodeBlockData({ title: val }));
                  }}
                  style={{
                     fontWeight: 600,
                     fontSize: "14px",
                     padding: 0,
                     flex: hasTitle ? "0 1 auto" : "1 1 auto",
                     minWidth: hasTitle ? 120 : 80,
                     maxWidth: hasTitle ? 360 : "100%",
                     opacity: hasTitle || !effectiveReadonly ? 1 : 0
                  }}
               />
               {isExecuting && (
                  <Tag color="orange" style={{ borderRadius: 12 }}>
                     running…
                  </Tag>
               )}
            </div>

            <div
               className="code-block__header-right"
               style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flex: "0 0 auto",
                  marginLeft: "auto"
               }}
            >
               <Space size={4}>
                  {!readonly && (
                     <Tooltip title={isExecuting ? "Stop" : "Run"}>
                        <Button
                           type="text"
                           size="small"
                           danger={isExecuting}
                           icon={
                              isExecuting ? (
                                 <StopOutlined />
                              ) : (
                                 <PlayCircleOutlined />
                              )
                           }
                           onClick={isExecuting ? handleStop : handleRun}
                           style={{ minWidth: 0 }}
                        />
                     </Tooltip>
                  )}

                  <Tooltip title={showCode ? "Hide Code" : "Show Code"}>
                     <Button
                        type="text"
                        size="small"
                        icon={showCode ? <UpOutlined /> : <DownOutlined />}
                        onClick={toggleCode}
                        style={{ minWidth: 0 }}
                     />
                  </Tooltip>
               </Space>
            </div>
         </div>
      );

      return (
         <div
            className="kontext-notebook-editor code-block"
            style={{ marginBottom: 16 }}
         >
            <div
               style={{
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 8,
                  overflow: "hidden",
                  background: token.colorBgContainer
               }}
            >
               {SummaryCard}

               {showCode && (
                  <div
                     style={{
                        borderTop: "none",
                        overflow: "auto",
                        maxHeight: "400px",
                        backgroundColor: isDarkMode ? "#1e1e1e" : "#fcfcfc"
                     }}
                  >
                     <LazyCodeEditor
                        value={localCode}
                        onChange={(val) => {
                           setLocalCode(val);
                        }}
                        onBlur={() => {
                           onChange(buildCodeBlockData({ code: localCode }));
                        }}
                        height="auto"
                        maxHeight="400px"
                        minHeight="50px"
                        theme={isDarkMode ? "dark" : "light"}
                        editable={!effectiveReadonly}
                     />
                  </div>
               )}

               {cancelError && (
                  <div
                     style={{
                        borderTop: `1px solid ${token.colorBorderSecondary}`,
                        padding: "8px 12px",
                        color: token.colorError,
                        fontSize: 12
                     }}
                  >
                     {cancelError}
                  </div>
               )}

               {(outputs.length > 0 || isExecuting) && (
                  <div
                     style={{
                        borderTop: `1px solid ${token.colorBorderSecondary}`
                     }}
                  >
                     <CodeBlockOutputs
                        outputs={outputs}
                        isLoading={isExecuting}
                        executionRunId={executionRunId}
                        executionMode={executionMode}
                        lastExecuted={lastExecuted}
                        style={{ borderRadius: 0 }}
                     />
                  </div>
               )}
            </div>
         </div>
      );
   }
);

CodeBlockComponent.displayName = "CodeBlockComponent";
