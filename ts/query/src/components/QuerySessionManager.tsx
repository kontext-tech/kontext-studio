import { formatTimeAgo } from "@kontext-tech/common";
import {
   ArrowRightOutlined,
   DatabaseOutlined,
   InfoCircleOutlined,
   PlayCircleOutlined,
   PlusOutlined,
   SearchOutlined
} from "@kontext-tech/icons";
import { QuerySessionStatus } from "@kontext-tech/schema";
import {
   Badge,
   Button,
   Drawer,
   Empty,
   Flex,
   Form,
   Input,
   Modal,
   Space,
   theme,
   Tooltip,
   Typography
} from "antd";
import React, { useState } from "react";
import { useProjectQuerySessions } from "../hooks";
import { QuerySessionInfo } from "./QuerySessionInfo";

export interface QuerySessionManagerProps {
   projectId: string;
}

interface CreateSessionFormData {
   sessionName: string;
}

export const QuerySessionManager: React.FC<QuerySessionManagerProps> = ({
   projectId
}) => {
   const { token } = theme.useToken();
   const [showCreateModal, setShowCreateModal] = useState(false);
   const [showSelectModal, setShowSelectModal] = useState(false);
   const [showSessionSidebar, setShowSessionSidebar] = useState(false);
   const [createForm] = Form.useForm<CreateSessionFormData>();

   const {
      sessions,
      effectiveSession,
      hasActiveSessions,
      isSessionReady,
      createSession,
      selectSession,
      initializeSession
   } = useProjectQuerySessions(projectId);

   const currentSession = effectiveSession;
   const isSelectedSessionReady = currentSession?.id
      ? isSessionReady(currentSession.id)
      : false;

   const handleCreateSession = async (values: CreateSessionFormData) => {
      const newSession = await createSession({
         sessionName: values.sessionName
      });

      if (newSession) {
         setShowCreateModal(false);
         createForm.resetFields();

         if (newSession.id) {
            await initializeSession(newSession.id);
         }
      }
   };

   const handleSelectSession = (selectedSessionId: string) => {
      selectSession(selectedSessionId);
      setShowSelectModal(false);
   };

   const handleInitializeSession = async () => {
      if (currentSession?.id) {
         await initializeSession(currentSession.id);
      }
   };

   const openCreateModal = () => {
      createForm.setFieldsValue({
         sessionName: `Session ${new Date().toLocaleString()}`
      });
      setShowCreateModal(true);
   };

   return (
      <Flex align="center" gap="middle">
         {!currentSession && !hasActiveSessions && (
            <Button
               type="primary"
               icon={<PlusOutlined />}
               onClick={openCreateModal}
               size="middle"
            >
               Create Session
            </Button>
         )}

         {!currentSession && hasActiveSessions && (
            <Button
               type="default"
               icon={<SearchOutlined />}
               onClick={() => setShowSelectModal(true)}
               size="middle"
            >
               Select Session
            </Button>
         )}

         {currentSession && (
            <Flex align="center" gap="small">
               <Flex align="center" gap="small">
                  <DatabaseOutlined style={{ color: token.colorPrimary }} />
                  <Typography.Text
                     strong
                     ellipsis={{
                        tooltip:
                           currentSession.sessionName ||
                           `Session ${currentSession.id?.slice(0, 8)}`
                     }}
                     style={{
                        maxWidth: "180px",
                        color: token.colorText
                     }}
                  >
                     {currentSession.sessionName ||
                        `Session ${currentSession.id?.slice(0, 8)}`}
                  </Typography.Text>
                  {isSelectedSessionReady && (
                     <Badge status="success" style={{ marginLeft: "4px" }} />
                  )}
               </Flex>
               <Space.Compact>
                  {!isSelectedSessionReady && (
                     <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        onClick={handleInitializeSession}
                        size="small"
                     >
                        Initialize
                     </Button>
                  )}
                  {sessions.length > 0 && (
                     <Tooltip title="Switch session">
                        <Button
                           type="text"
                           icon={<SearchOutlined />}
                           onClick={() => setShowSelectModal(true)}
                           size="small"
                           style={{ color: token.colorTextSecondary }}
                        />
                     </Tooltip>
                  )}
                  <Tooltip title="Create a new session">
                     <Button
                        type="text"
                        icon={<PlusOutlined />}
                        onClick={openCreateModal}
                        size="small"
                        style={{ color: token.colorTextSecondary }}
                     />
                  </Tooltip>
                  <Tooltip title="Session details">
                     <Button
                        type="text"
                        icon={<InfoCircleOutlined />}
                        onClick={() => setShowSessionSidebar(true)}
                        size="small"
                        style={{ color: token.colorTextSecondary }}
                     />
                  </Tooltip>
               </Space.Compact>
            </Flex>
         )}

         <Modal
            title={
               <Flex align="center" gap="small">
                  <PlusOutlined />
                  <span>Create New Session</span>
               </Flex>
            }
            open={showCreateModal}
            onCancel={() => {
               setShowCreateModal(false);
               createForm.resetFields();
            }}
            footer={null}
            width={480}
         >
            <Form
               form={createForm}
               layout="vertical"
               onFinish={handleCreateSession}
               style={{ marginTop: "16px" }}
            >
               <Form.Item
                  name="sessionName"
                  label="Session Name"
                  rules={[
                     { required: true, message: "Please enter a session name" },
                     {
                        max: 100,
                        message: "Session name cannot exceed 100 characters"
                     }
                  ]}
               >
                  <Input
                     placeholder="Enter a descriptive session name"
                     showCount
                     maxLength={100}
                  />
               </Form.Item>
               <Form.Item style={{ marginBottom: 0, marginTop: "24px" }}>
                  <Flex justify="end" gap="small">
                     <Button
                        onClick={() => {
                           setShowCreateModal(false);
                           createForm.resetFields();
                        }}
                     >
                        Cancel
                     </Button>
                     <Button
                        type="primary"
                        htmlType="submit"
                        icon={<PlusOutlined />}
                     >
                        Create Session
                     </Button>
                  </Flex>
               </Form.Item>
            </Form>
         </Modal>

         <Modal
            title={
               <Flex align="center" gap="small">
                  <SearchOutlined />
                  <span>Select Session</span>
               </Flex>
            }
            open={showSelectModal}
            onCancel={() => setShowSelectModal(false)}
            footer={null}
            width={640}
            styles={{ body: { padding: "8px 0" } }}
         >
            {sessions.length === 0 ? (
               <Empty
                  description="No sessions found"
                  style={{ margin: "32px 0" }}
               />
            ) : (
               <Flex vertical gap="small" style={{ padding: "0 24px" }}>
                  {sessions.map((session) => {
                     const isSelected = currentSession?.id === session.id;

                     return (
                        <Flex
                           key={session.id}
                           align="center"
                           gap="middle"
                           style={{
                              padding: "16px",
                              cursor: isSelected ? "default" : "pointer",
                              backgroundColor: isSelected
                                 ? token.colorPrimaryBg
                                 : "transparent",
                              borderRadius: "6px",
                              border: isSelected
                                 ? `1px solid ${token.colorPrimary}`
                                 : "1px solid transparent",
                              transition: "all 0.2s"
                           }}
                           onClick={() =>
                              !isSelected && handleSelectSession(session.id!)
                           }
                        >
                           <DatabaseOutlined
                              style={{
                                 fontSize: token.fontSizeLG,
                                 color: isSelected
                                    ? token.colorPrimary
                                    : token.colorTextSecondary
                              }}
                           />
                           <Flex vertical flex={1} gap="small">
                              <Typography.Text
                                 strong
                                 style={{
                                    fontSize: token.fontSize,
                                    color: isSelected
                                       ? token.colorPrimary
                                       : token.colorText
                                 }}
                              >
                                 {session.sessionName ||
                                    `Session ${session.id?.slice(0, 8)}`}
                              </Typography.Text>
                              <Space size="middle" wrap>
                                 <Badge
                                    status={
                                       session.status ===
                                       QuerySessionStatus.Active
                                          ? "success"
                                          : session.status ===
                                              QuerySessionStatus.Error
                                            ? "error"
                                            : "processing"
                                    }
                                    text={
                                       <Typography.Text
                                          type="secondary"
                                          style={{ fontSize: token.fontSizeSM }}
                                       >
                                          {session.status}
                                       </Typography.Text>
                                    }
                                 />
                                 {session.defaultNamespace && (
                                    <Typography.Text
                                       type="secondary"
                                       style={{ fontSize: token.fontSizeSM }}
                                    >
                                       Namespace: {session.defaultNamespace}
                                    </Typography.Text>
                                 )}
                                 {session.createdAt && (
                                    <Typography.Text
                                       type="secondary"
                                       style={{ fontSize: token.fontSizeSM }}
                                    >
                                       Created:{" "}
                                       {formatTimeAgo(session.createdAt)}
                                    </Typography.Text>
                                 )}
                              </Space>
                           </Flex>
                           {isSelected ? (
                              <Badge
                                 count="Selected"
                                 style={{
                                    backgroundColor: token.colorPrimary,
                                    fontSize: token.fontSizeSM,
                                    height: "18px",
                                    lineHeight: "18px",
                                    borderRadius: "9px"
                                 }}
                              />
                           ) : (
                              <Tooltip title="Select this session">
                                 <Button
                                    type="primary"
                                    ghost
                                    shape="circle"
                                    icon={<ArrowRightOutlined />}
                                    onClick={(event) => {
                                       event.stopPropagation();
                                       handleSelectSession(session.id!);
                                    }}
                                    size="small"
                                 />
                              </Tooltip>
                           )}
                        </Flex>
                     );
                  })}
               </Flex>
            )}
         </Modal>

         {currentSession && (
            <Drawer
               title="Session Details"
               open={showSessionSidebar}
               onClose={() => setShowSessionSidebar(false)}
               size="large"
               placement="right"
            >
               <QuerySessionInfo
                  projectId={projectId}
                  sessionId={currentSession.id!}
                  onClose={() => setShowSessionSidebar(false)}
               />
            </Drawer>
         )}
      </Flex>
   );
};
