import { ProjectRoleTags } from "@kontext-labs/auth";
import {
   getUserDisplayName,
   UserAvatar,
   useUser
} from "@kontext-labs/identity";
import { useUiApp } from "@kontext-labs/ui";
import {
   DeleteOutlined,
   EditOutlined,
   QuestionCircleOutlined,
   UserOutlined
} from "@kontext-labs/icons";
import type { UserWithProjectRolesModel } from "@kontext-labs/schema";
import { Button, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

export interface ProjectUsersTableProps {
   users: UserWithProjectRolesModel[];
   isLoading: boolean;
   screens: Record<string, boolean>;
   onEditUser: (user: UserWithProjectRolesModel) => void;
   onRemoveUser: (userId: string) => void;
}

const ProjectUsersTable: React.FC<ProjectUsersTableProps> = ({
   users,
   isLoading,
   screens,
   onEditUser,
   onRemoveUser
}) => {
   const { user: currentUser } = useUser();
   const { modal } = useUiApp();

   const columns: ColumnsType<UserWithProjectRolesModel> = [
      {
         title: "User",
         dataIndex: "displayName",
         key: "displayName",
         render: (_: string, record: UserWithProjectRolesModel) => (
            <UserAvatar
               user={record}
               size="small"
               showName={true}
               namePosition="right"
            />
         )
      },
      {
         title: "User ID",
         dataIndex: "id",
         key: "id",
         render: (id: string) => (
            <Typography.Text copyable={{ text: id }} style={{ maxWidth: 150 }}>
               {id}
            </Typography.Text>
         )
      },
      {
         title: "Roles",
         dataIndex: "projectRoles",
         key: "projectRoles",
         render: (roles: string[]) =>
            roles && roles.length > 0 ? (
               <ProjectRoleTags roles={roles} />
            ) : (
               <Tag>No roles</Tag>
            )
      },
      {
         title: "Actions",
         key: "actions",
         align: "center",
         render: (_: unknown, record: UserWithProjectRolesModel) => {
            const isCurrentUser = currentUser?.id === record.id;
            const displayName = getUserDisplayName(record);

            return (
               <Space size="small">
                  {isCurrentUser ? (
                     <Tooltip title="This is you">
                        <Typography.Text type="secondary">
                           <UserOutlined />
                        </Typography.Text>
                     </Tooltip>
                  ) : null}
                  <Tooltip title="Edit Roles">
                     <Button
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => onEditUser(record)}
                        aria-label={`Edit roles for ${displayName}`}
                     />
                  </Tooltip>
                  <Tooltip
                     title={
                        isCurrentUser
                           ? "You cannot remove yourself from the project"
                           : "Remove User"
                     }
                  >
                     <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        disabled={isCurrentUser}
                        onClick={() => {
                           modal.confirm({
                              title: "Remove User",
                              content: `Are you sure you want to remove ${displayName} from this project?`,
                              onOk: () => record.id && onRemoveUser(record.id),
                              okText: "Yes, Remove",
                              cancelText: "No",
                              icon: (
                                 <QuestionCircleOutlined
                                    style={{ color: "red" }}
                                 />
                              ),
                              okButtonProps: { danger: true }
                           });
                        }}
                        aria-label={`Remove ${displayName} from project`}
                     />
                  </Tooltip>
               </Space>
            );
         }
      }
   ];

   return (
      <Table
         dataSource={users}
         columns={columns}
         rowKey="id"
         pagination={false}
         size="middle"
         loading={isLoading}
         scroll={screens.md ? undefined : { x: 800 }}
      />
   );
};

export default ProjectUsersTable;
