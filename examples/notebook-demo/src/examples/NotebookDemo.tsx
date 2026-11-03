import { logoDark, logoLight } from "@kontext-tech/common";
import { DatabaseZapOutlined } from "@kontext-tech/icons";
import {
   NotebookEditor,
   NotebookServiceProvider,
   useNotebookStore,
   type CellExecutionContext,
   type NotebookDocument,
   type SidebarTabExtension
} from "@kontext-tech/notebook";
import { useQuerySessionStore } from "@kontext-tech/query";
import { QueryEngineType, QuerySessionStatus } from "@kontext-tech/schema";
import { App } from "antd";
import React, { useCallback, useEffect, useMemo, useRef } from "react";
import NotebookSessionsSidebarTab from "../extensions/NotebookSessionsSidebarTab";
import { MockResourceService } from "../services/mock-resource-service";
import { MockQuerySessionService } from "../services/mock-session-service";
import { EXAMPLE_DATA_TABLES } from "./example-data-tables";
import { EXAMPLE_NOTEBOOK } from "./example-notebook-data";

const DEMO_PROJECT_ID = "550e8400-e29b-41d4-a716-446655440000";
const DEMO_INSTANCE_ID = "notebook-demo";

interface NotebookDemoContentProps {
   mockResourceService: MockResourceService;
   mockSessionService: MockQuerySessionService;
   isDarkMode?: boolean;
}

const NotebookDemoContent: React.FC<NotebookDemoContentProps> = ({
   mockResourceService,
   mockSessionService,
   isDarkMode = false
}) => {
   const { message } = App.useApp();
   const hasInitialized = useRef(false);

   const createInstance = useNotebookStore((state) => state.createInstance);
   const removeInstance = useNotebookStore((state) => state.removeInstance);
   const setTheme = useNotebookStore((state) => state.setTheme);
   const isInitialized = useNotebookStore(
      (state) => !!state.getInstanceState(DEMO_INSTANCE_ID)?.isInitialized
   );
   const storeDocument = useNotebookStore(
      (state) => state.getInstanceState(DEMO_INSTANCE_ID)?.document ?? null
   );

   const cultures = useMemo(
      () => [
         {
            code: "en",
            displayName: "English",
            nativeName: "English",
            isRightToLeft: false
         },
         {
            code: "zh",
            displayName: "Chinese",
            nativeName: "中文",
            isRightToLeft: false
         }
      ],
      []
   );
   const sidebarExtensions = useMemo<SidebarTabExtension[]>(() => {
      return [
         {
            key: "sessions",
            label: "Sessions",
            icon: <DatabaseZapOutlined />,
            children: <NotebookSessionsSidebarTab projectId={DEMO_PROJECT_ID} />
         }
      ];
   }, []);

   const handleSave = useCallback(
      async (doc: NotebookDocument) => {
         try {
            await new Promise((resolve) => setTimeout(resolve, 500));
            message.success("Notebook saved successfully!");
            console.log("Document saved:", doc);
         } catch (error) {
            message.error("Failed to save notebook");
            console.error("Error saving document:", error);
         }
      },
      [message]
   );

   const setQuerySessions = useQuerySessionStore((state) => state.setSessions);
   const setServiceOverrides = useQuerySessionStore(
      (state) => state.setServiceOverrides
   );
   const setSelectedSession = useQuerySessionStore(
      (state) => state.setSelectedSession
   );

   useEffect(() => {
      if (!hasInitialized.current) {
         hasInitialized.current = true;

         setServiceOverrides({
            sessionService: mockSessionService,
            queryService: mockSessionService
         });

         const mockSessions = [
            {
               id: "session-1",
               sessionName: "Demo Query Session",
               projectId: DEMO_PROJECT_ID,
               status: QuerySessionStatus.Active,
               ownerId: "demo-user",
               engineType: QueryEngineType.DuckDB,
               createdAt: new Date(Date.now() - 86400000).toISOString(),
               updatedAt: new Date(Date.now() - 3600000).toISOString(),
               lastAccessedAt: new Date(Date.now() - 3600000).toISOString(),
               isPersistent: true
            }
         ];

         setQuerySessions(mockSessions);
         setSelectedSession(DEMO_PROJECT_ID, mockSessions[0]?.id || null);

         const initialDocument = JSON.parse(
            JSON.stringify(EXAMPLE_NOTEBOOK)
         ) as NotebookDocument;

         if (
            initialDocument.blocks.length > 0 &&
            initialDocument.blocks[0].type === "image"
         ) {
            initialDocument.blocks[0].data.file = {
               url: isDarkMode ? logoDark : logoLight
            };
         }

         if (initialDocument.metadata) {
            initialDocument.metadata.imageUrl = isDarkMode
               ? logoDark
               : logoLight;
         }

         createInstance(DEMO_INSTANCE_ID, {
            document: initialDocument,
            isDarkMode,
            readonly: false
         });
      }

      return () => {
         if (import.meta.env.PROD) {
            removeInstance(DEMO_INSTANCE_ID);
            mockResourceService.clearAll();
            setServiceOverrides(null);
         }
      };
   }, [
      createInstance,
      isDarkMode,
      mockResourceService,
      mockSessionService,
      removeInstance,
      setServiceOverrides,
      setSelectedSession,
      setQuerySessions
   ]);

   useEffect(() => {
      if (isInitialized) {
         setTheme(isDarkMode, DEMO_INSTANCE_ID);
      }
   }, [isDarkMode, isInitialized, setTheme]);

   if (!isInitialized || !storeDocument) {
      return <div>Loading...</div>;
   }

   return (
      <div
         style={{
            display: "flex",
            flexDirection: "column",
            height: "100vh"
         }}
      >
         <div style={{ flex: 1, overflow: "hidden" }}>
            <NotebookEditor
               instanceId={DEMO_INSTANCE_ID}
               onSave={handleSave}
               cultures={cultures}
               projectId={DEMO_PROJECT_ID}
               sidebarExtensions={sidebarExtensions}
               enableSqlBlock
               enableChartBlock
               showArticleMetadata
            />
         </div>
      </div>
   );
};

interface NotebookDemoProps {
   isDarkMode?: boolean;
}

const NotebookDemo: React.FC<NotebookDemoProps> = ({ isDarkMode = false }) => {
   const mockResourceService = useMemo(() => {
      const service = new MockResourceService();

      Object.entries(EXAMPLE_DATA_TABLES).forEach(
         ([resourceId, inlineData]) => {
            service.storeInlineData(resourceId, inlineData);
         }
      );

      const canvas = document.createElement("canvas");
      canvas.width = 400;
      canvas.height = 300;
      const ctx = canvas.getContext("2d");

      if (ctx) {
         const gradient = ctx.createLinearGradient(0, 0, 400, 300);
         gradient.addColorStop(0, "#4A90E2");
         gradient.addColorStop(1, "#7B68EE");
         ctx.fillStyle = gradient;
         ctx.fillRect(0, 0, 400, 300);

         ctx.fillStyle = "white";
         ctx.font = "bold 32px Arial";
         ctx.textAlign = "center";
         ctx.fillText("Sample Image", 200, 140);
         ctx.font = "18px Arial";
         ctx.fillText("Kontext Demo", 200, 170);
      }

      const dataUrl = canvas.toDataURL("image/png");

      const dataURLToBlob = (value: string): Blob => {
         const parts = value.split(",");
         const mimeMatch = parts[0].match(/:(.*?);/);
         const mime = mimeMatch ? mimeMatch[1] : "image/png";
         const binary = atob(parts[1]);
         const bytes = new Uint8Array(binary.length);

         for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
         }

         return new Blob([bytes], { type: mime });
      };

      const blob = dataURLToBlob(dataUrl);
      const sampleResource = {
         id: "sample",
         name: "sample-image.png",
         contentType: "image/png",
         blob,
         projectId: DEMO_PROJECT_ID,
         ownerId: "demo-user",
         size: blob.size,
         dateCreated: new Date().toISOString(),
         dateModified: new Date().toISOString()
      };

      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore - test fixture hydration for the demo image store
      service.resources.set("sample", sampleResource);

      return service;
   }, []);

   const mockSessionService = useMemo(
      () => new MockQuerySessionService(mockResourceService),
      [mockResourceService]
   );

   const fileSystem = useMemo(
      () => ({
         uploadImage: (
            fileOrProjectId: File | Blob | string,
            file?: File | Blob
         ) => {
            if (typeof fileOrProjectId === "string") {
               return mockResourceService.uploadImage(
                  fileOrProjectId,
                  file ?? new Blob()
               );
            }

            return mockResourceService.uploadImage(
               DEMO_PROJECT_ID,
               fileOrProjectId
            );
         },
         getFileUrl: (fileId: string) => mockResourceService.getFileUrl(fileId),
         getInlineData: async (fileId: string, projectId?: string) => {
            const result = await mockResourceService.getDataTableFile(
               fileId,
               projectId || DEMO_PROJECT_ID
            );

            if (!result.succeed || !result.data?.table) {
               return {
                  succeed: false,
                  error: result.error
               };
            }

            return {
               succeed: true,
               data: result.data.table
            };
         },
         downloadFile: (
            fileId: string,
            projectId?: string,
            onProgress?: (progress: number) => void
         ) =>
            mockResourceService.downloadFile(
               fileId,
               projectId || DEMO_PROJECT_ID,
               onProgress
            ),
         getPaginatedImageFiles: (
            projectId?: string,
            pageIndex = 0,
            pageSize = 20,
            search = ""
         ) =>
            mockResourceService.getPaginatedImageFiles(
               projectId || DEMO_PROJECT_ID,
               pageIndex,
               pageSize,
               search
            )
      }),
      [mockResourceService]
   );

   const executionEngine = useMemo(() => {
      const executeCell = async (
         language: string,
         code: string,
         context?: CellExecutionContext
      ) => {
         if (language.toLowerCase() !== "sql") {
            return {
               status: "error" as const,
               error: `${language} execution is not implemented yet.`
            };
         }

         const selectedSession =
            useQuerySessionStore
               .getState()
               .getSelectedSession(DEMO_PROJECT_ID) ||
            useQuerySessionStore
               .getState()
               .getActiveSessions(DEMO_PROJECT_ID)[0];

         if (!selectedSession?.id) {
            return {
               status: "error" as const,
               error: "No session selected for this project. Please select a session first."
            };
         }

         const response = await mockSessionService.executeQuery({
            projectId: DEMO_PROJECT_ID,
            sessionId: selectedSession.id,
            sqlQuery: code,
            storeResultAsResource: false,
            triggeredBy: context?.notebookId
               ? { type: "Notebook" as const, id: context.notebookId }
               : { type: "User" as const, id: "demo-user" }
         });

         if (
            !response.succeed ||
            !response.data ||
            response.data.success === false
         ) {
            return {
               status: "error" as const,
               error:
                  response.data?.errorMessage ||
                  response.error?.messages.join(", ") ||
                  "SQL execution failed."
            };
         }

         return {
            status: "success" as const,
            output: {
               dataId: response.data.dataId || undefined,
               inlineData: response.data.result || undefined
            },
            executionTimeMs: response.data.totalExecutionTimeMs ?? undefined
         };
      };

      const execute = async (
         code: string,
         context?: CellExecutionContext,
         language = "python"
      ) => {
         if (language.toLowerCase() === "sql") {
            const result = await executeCell("sql", code, context);

            if (result.status === "error") {
               return {
                  status: "error" as const,
                  outputs: [
                     {
                        type: "text" as const,
                        mimeType: "text/plain",
                        content: result?.error || "SQL execution failed."
                     }
                  ],
                  error: result.error || "SQL execution failed.",
                  executionTimeMs: result.executionTimeMs
               };
            }

            return {
               status: "success" as const,
               outputs: [
                  {
                     type: "text" as const,
                     mimeType: "text/plain",
                     content: "SQL cell executed successfully."
                  }
               ],
               executionTimeMs: result.executionTimeMs
            };
         }

         const nextError = `${language} execution is not implemented yet.`;
         return {
            status: "error" as const,
            outputs: [
               {
                  type: "text" as const,
                  mimeType: "text/plain",
                  content: nextError
               }
            ],
            error: nextError
         };
      };

      return {
         execute,
         executeCell,
         cancelExecution: async () => false
      };
   }, [mockSessionService]);

   return (
      <NotebookServiceProvider
         projectId={DEMO_PROJECT_ID}
         fileSystem={fileSystem}
         executionEngine={executionEngine}
      >
         <NotebookDemoContent
            mockResourceService={mockResourceService}
            mockSessionService={mockSessionService}
            isDarkMode={isDarkMode}
         />
      </NotebookServiceProvider>
   );
};

export default NotebookDemo;
