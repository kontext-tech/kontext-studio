import { PAGE_SIZE_OPTIONS } from "@kontext-tech/common";
import { getFullUrl } from "@kontext-tech/common/utils";
import { QuestionCircleOutlined, UserAddOutlined } from "@kontext-tech/icons";
import type { ApiErrorResult } from "@kontext-tech/common/types";
import type { UserWithProjectRolesModel } from "@kontext-tech/schema";
import { DebouncedSearch } from "@kontext-tech/ui";
import {
   Alert,
   Button,
   Empty,
   Flex,
   Form,
   Grid,
   Pagination,
   Space,
   Tooltip
} from "antd";
import { useState } from "react";
import { useProjectUsers } from "../../useProjectUsers";
import AddUserModal from "./AddUserModal";
import EditUserModal from "./EditUserModal";
import ProjectUsersTable from "./ProjectUsersTable";

const { useBreakpoint } = Grid;

export interface ProjectUsersProps {
   projectId: string;
   isLocalMode?: boolean;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

const ProjectUsers: React.FC<ProjectUsersProps> = ({
   projectId,
   isLocalMode = false,
   errorHandler
}) => {
   const [isAddModalVisible, setIsAddModalVisible] = useState(false);
   const [isEditModalVisible, setIsEditModalVisible] = useState(false);
   const [editingUser, setEditingUser] =
      useState<UserWithProjectRolesModel | null>(null);

   const [addForm] = Form.useForm();
   const [editForm] = Form.useForm();

   const {
      users,
      isLoading,
      error,
      pageIndex,
      pageSize,
      totalCount,
      filter,
      isSubmitting,
      setPageIndex,
      setPageSize,
      handleSearch,
      handleAddUser,
      handleEditUserRoles,
      handleRemoveUser
   } = useProjectUsers(projectId, errorHandler);

   const screens = useBreakpoint();

   const handleCancel = () => {
      setIsAddModalVisible(false);
      setIsEditModalVisible(false);
      setEditingUser(null);
   };

   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="large">
         <Flex justify="space-between" align="center" wrap="wrap" gap="middle">
            <Flex align="center" gap="middle">
               <DebouncedSearch
                  placeholder="Search users..."
                  onSearch={handleSearch}
                  style={{ width: 300 }}
                  allowClear
               />
            </Flex>

            <Flex align="center" gap="middle">
               <Tooltip
                  title={
                     isLocalMode
                        ? "Adding users is disabled for local projects"
                        : undefined
                  }
               >
                  <Button
                     type="primary"
                     icon={<UserAddOutlined />}
                     onClick={() => !isLocalMode && setIsAddModalVisible(true)}
                     disabled={isLocalMode}
                  >
                     Add User
                  </Button>
               </Tooltip>

               <Tooltip title="Read guide: Project roles and permissions">
                  <a
                     href={getFullUrl("docs/project-management-permissions")}
                     target="_blank"
                     rel="noopener noreferrer"
                     aria-label="Project roles and permissions guide"
                  >
                     <QuestionCircleOutlined />
                  </a>
               </Tooltip>
            </Flex>
         </Flex>

         {error ? <Alert type="error" title={error}></Alert> : null}
         {isLocalMode ? (
            <Alert
               type="info"
               title="Local projects do not allow adding new users."
               showIcon
            />
         ) : null}

         {users.length === 0 && !isLoading ? (
            <Empty
               description={
                  filter
                     ? "No users found matching your search"
                     : "No users found"
               }
               image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
         ) : (
            <ProjectUsersTable
               users={users}
               isLoading={isLoading}
               screens={screens}
               onEditUser={(user) => {
                  setEditingUser(user);
                  setIsEditModalVisible(true);
               }}
               onRemoveUser={handleRemoveUser}
            />
         )}

         {totalCount > 0 ? (
            <Flex justify="flex-end">
               <Pagination
                  current={pageIndex}
                  pageSize={pageSize}
                  total={totalCount}
                  pageSizeOptions={PAGE_SIZE_OPTIONS}
                  showSizeChanger
                  showTotal={(total) => `Total ${total} users`}
                  onChange={(page, size) => {
                     setPageIndex(page);
                     if (size) setPageSize(size);
                  }}
               />
            </Flex>
         ) : null}

         <AddUserModal
            isVisible={isAddModalVisible}
            isSubmitting={isSubmitting}
            form={addForm}
            onOk={async (values) => {
               if (isLocalMode) return;

               const success = await handleAddUser(values);
               if (success) {
                  setIsAddModalVisible(false);
               }
            }}
            onCancel={handleCancel}
         />

         <EditUserModal
            isVisible={isEditModalVisible}
            isSubmitting={isSubmitting}
            form={editForm}
            editingUser={editingUser}
            onOk={async (values) => {
               if (!editingUser?.id) return;

               const success = await handleEditUserRoles(
                  editingUser.id,
                  values
               );
               if (success) {
                  setIsEditModalVisible(false);
                  setEditingUser(null);
               }
            }}
            onCancel={handleCancel}
         />
      </Space>
   );
};

export default ProjectUsers;
