import PageContainer from "@/components/layout/SeoPageContainer";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { ChatSessionList, useChatSessionStore } from "@kontext-labs/chat";
import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import { FilterOutlined, PlusOutlined } from "@kontext-labs/icons";
import { useUserStore } from "@kontext-labs/identity";
import { useProject } from "@kontext-labs/project";
import { type ChatSessionModel, type ProjectModel } from "@kontext-labs/schema";
import { DebouncedSearch, LoadingSpinner, useUiApp } from "@kontext-labs/ui";
import {
   Button,
   Checkbox,
   Dropdown,
   Empty,
   Flex,
   Pagination,
   Space
} from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

dayjs.extend(relativeTime);

const ChatSessionListPageInternal = ({
   project
}: {
   project: ProjectModel;
}) => {
   const { getProjectChatSessionDetailPath, getRoutePath } = useRoute();
   const navigate = useNavigate();
   const { message, modal } = useUiApp();
   const [sessions, setSessions] = useState<ChatSessionModel[]>([]);
   const [isLoading, setIsLoading] = useState(true);
   const [pageIndex, setPageIndex] = useState(1);
   const [pageSize, setPageSize] = useState(10);
   const [total, setTotal] = useState(0);
   const [filter, setFilter] = useState("");
   const [mySessionsOnly, setMySessionsOnly] = useState(false);

   const deleteChatSession = useChatSessionStore(
      (state) => state.deleteChatSession
   );
   const getFilteredChatSessions = useChatSessionStore(
      (state) => state.getFilteredChatSessions
   );
   const chatService = useChatSessionStore((state) => state.chatService);
   const tokens = useUserStore((state) => state.tokens);
   const authContext = useMemo(
      () => ({
         accessToken: tokens?.accessToken
      }),
      [tokens?.accessToken]
   );

   const fetchSessions = useCallback(async () => {
      if (!project.id) return;
      if (!authContext.accessToken) return;
      if (!chatService) return; // store service is initialized by ChatSessionStoreProvider

      setIsLoading(true);
      try {
         const result = await getFilteredChatSessions(
            filter || undefined,
            pageIndex,
            pageSize,
            mySessionsOnly
         );
         if (result.succeed && result.data) {
            setSessions(result.data.items);
            setTotal(result.data.totalCount || 0);
         }
      } catch (error) {
         console.error("Failed to fetch chats", error);
      } finally {
         setIsLoading(false);
      }
   }, [
      project,
      authContext,
      chatService,
      getFilteredChatSessions,
      filter,
      pageIndex,
      pageSize,
      mySessionsOnly
   ]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void fetchSessions();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [fetchSessions]);

   const handleDelete = (session: ChatSessionModel) => {
      modal.confirm({
         title: "Delete Chat",
         content: `Are you sure you want to delete "${session.sessionName || "Untitled Chat"}"?`,
         okText: "Delete",
         okType: "danger",
         cancelText: "Cancel",
         onOk: async () => {
            const success = await deleteChatSession(session.id);
            if (success) {
               message.success("Chat deleted");
               fetchSessions();
            } else {
               message.error("Failed to delete chat");
            }
         }
      });
   };

   const handleOpenSession = (session: ChatSessionModel) => {
      const path = getProjectChatSessionDetailPath(
         project,
         session.id,
         session.sessionName
      );
      navigate(path);
   };

   return (
      <PageContainer
         title="Chats"
         routeName={RouteNames.PROJECT_CHAT_SESSIONS}
         project={project}
         showBreadcrumb={false}
         actions={
            <Space>
               <DebouncedSearch
                  placeholder="Search chats..."
                  onSearch={(value) => {
                     setFilter(value);
                     setPageIndex(1);
                  }}
                  style={{ width: 250 }}
               />
               <Dropdown
                  menu={{
                     items: [
                        {
                           key: "my-sessions",
                           label: (
                              <Checkbox
                                 checked={mySessionsOnly}
                                 onChange={(e) => {
                                    setMySessionsOnly(e.target.checked);
                                    setPageIndex(1);
                                 }}
                              >
                                 My Chats Only
                              </Checkbox>
                           )
                        }
                     ]
                  }}
                  trigger={["click"]}
               >
                  <Button icon={<FilterOutlined />}>Filter</Button>
               </Dropdown>
               <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() =>
                     navigate(getRoutePath(RouteNames.PROJECT, project))
                  }
               >
                  New Chat
               </Button>
            </Space>
         }
      >
         <Flex vertical gap="middle">
            {isLoading ? (
               <LoadingSpinner style={{ minHeight: 200 }} />
            ) : sessions.length > 0 ? (
               <>
                  <ChatSessionList
                     sessions={sessions}
                     onOpen={handleOpenSession}
                     onDelete={handleDelete}
                     projects={[project]}
                     showProjectName={false}
                     showAvatar={true}
                     showAgentInfo={false}
                  />
                  <Flex justify="end">
                     <Pagination
                        current={pageIndex}
                        pageSize={pageSize}
                        total={total}
                        showSizeChanger
                        pageSizeOptions={PAGE_SIZE_OPTIONS}
                        onChange={(page, size) => {
                           if (size) setPageSize(size);
                           setPageIndex(page);
                        }}
                        onShowSizeChange={(current, size) => {
                           setPageSize(size);
                           setPageIndex(current);
                        }}
                     />
                  </Flex>
               </>
            ) : (
               <Empty description="No chats found" />
            )}
         </Flex>
      </PageContainer>
   );
};

const ChatSessionListPage = () => {
   const { currentProject, isProjectLoading } = useProject();

   if (isProjectLoading) {
      return (
         <PageContainer
            title="Loading..."
            routeName={RouteNames.PROJECT_CHAT_SESSIONS}
         >
            <LoadingSpinner style={{ minHeight: 200 }} />
         </PageContainer>
      );
   }

   if (!currentProject) {
      return null;
   }

   return <ChatSessionListPageInternal project={currentProject} />;
};

export default ChatSessionListPage;
