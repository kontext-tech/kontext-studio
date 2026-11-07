import { PermissionSearch } from "@kontext-tech/auth";
import { PermissionSelect } from "@kontext-tech/auth";
import PageContainer from "@/components/layout/SeoPageContainer";
import {
   DownloadProgressModal,
   FileActions,
   FILE_PREFIX_QUERY_PARAM,
   FILE_TYPE_QUERY_PARAM,
   FileUploadModal,
   ImagePreviewModal,
   useFileWorkflow
} from "@kontext-tech/file";
import { CreateNotebookModal } from "@kontext-tech/notebook";
import { useProject } from "@kontext-tech/project";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { UserAvatarById } from "@kontext-tech/identity";
import { FolderOutlined } from "@ant-design/icons";
import {
   CommonRoleGroups,
   PermissionButton,
   ProjectRole
} from "@kontext-tech/auth";
import { PAGE_SIZE_OPTIONS, SEARCH_QUERY_PARAM } from "@kontext-tech/common";
import { formatFileSize, formatTimeAgo } from "@kontext-tech/common";
import {
   DownOutlined,
   NotebookOutlined,
   PlusOutlined,
   UploadOutlined
} from "@kontext-tech/icons";
import { FileFormatType, type FileModel } from "@kontext-tech/schema";
import { FileIcon } from "@kontext-tech/ui";
import {
   Breadcrumb,
   Dropdown,
   Flex,
   Space,
   Table,
   Tooltip,
   type MenuProps
} from "antd";
import type { TablePaginationConfig } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

type FileListPageProject = NonNullable<
   ReturnType<typeof useProject>["currentProject"]
>;

const DIRECTORY_CONTENT_TYPE = "inode/directory";
const FILE_ICON_STYLE = { fontSize: 20 };
const BREADCRUMB_ICON_STYLE = { fontSize: 14, marginRight: 6 };
const HIDDEN_SYSTEM_PREFIXES = [".knowledge", ".lakehouse", ".okf"];

const isFolderEntry = (file: FileModel): boolean =>
   file.contentType === DIRECTORY_CONTENT_TYPE;

const isSystemManagedPrefix = (prefix: string): boolean =>
   HIDDEN_SYSTEM_PREFIXES.some(
      (systemPrefix) =>
         prefix === systemPrefix || prefix.startsWith(`${systemPrefix}/`)
   );

const FileListPageContent = ({
   currentProject
}: {
   currentProject: FileListPageProject;
}) => {
   const navigate = useNavigate();
   const [searchParams, setSearchParams] = useSearchParams();
   const { getFileDetailPath, getNotebookDetailPath, getRoutePath } =
      useRoute();
   const [isModalVisible, setIsModalVisible] = useState<boolean>(false);
   const [isNotebookModalVisible, setIsNotebookModalVisible] =
      useState<boolean>(false);
   const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
   const [isBulkDeleting, setIsBulkDeleting] = useState<boolean>(false);

   // Preview state
   const [previewVisible, setPreviewVisible] = useState<boolean>(false);
   const [previewResource, setPreviewResource] = useState<FileModel | null>(
      null
   );

   // Helper functions for URL parameter management
   const getSearchFromUrl = useCallback((): string => {
      return searchParams.get(SEARCH_QUERY_PARAM) || "";
   }, [searchParams]);

   const getPrefixFromUrl = useCallback((): string => {
      return searchParams.get(FILE_PREFIX_QUERY_PARAM) || "";
   }, [searchParams]);

   const getFileFormatTypesFromUrl = useCallback((): FileFormatType[] => {
      const fileTypesParam = searchParams.get(FILE_TYPE_QUERY_PARAM);
      if (!fileTypesParam) return [];

      try {
         return fileTypesParam
            .split(",")
            .filter((type) =>
               Object.values(FileFormatType).includes(type as FileFormatType)
            )
            .map((type) => type as FileFormatType);
      } catch {
         return [];
      }
   }, [searchParams]);

   const updateUrlParams = useCallback(
      (searchValue?: string, fileTypes?: FileFormatType[], prefix?: string) => {
         const newParams = new URLSearchParams(searchParams);

         // Update search parameter
         if (searchValue !== undefined) {
            if (searchValue.trim()) {
               newParams.set(SEARCH_QUERY_PARAM, searchValue.trim());
            } else {
               newParams.delete(SEARCH_QUERY_PARAM);
            }
         }

         // Update file types parameter
         if (fileTypes !== undefined) {
            if (fileTypes.length > 0) {
               newParams.set(FILE_TYPE_QUERY_PARAM, fileTypes.join(","));
            } else {
               newParams.delete(FILE_TYPE_QUERY_PARAM);
            }
         }

         if (prefix !== undefined) {
            if (prefix.trim()) {
               newParams.set(FILE_PREFIX_QUERY_PARAM, prefix.trim());
            } else {
               newParams.delete(FILE_PREFIX_QUERY_PARAM);
            }
         }

         setSearchParams(newParams, { replace: true });
      },
      [searchParams, setSearchParams]
   );

   // Use the unified files hook with list management enabled
   const {
      listState,
      loadFiles,
      updateListState,
      downloadFile,
      deleteFile,
      deleteMultipleFiles,
      downloadProgress,
      downloadModalVisible,
      downloadModalText,
      closeDownloadModal
   } = useFileWorkflow({
      projectId: currentProject.id,
      enableListManagement: true,
      initialPageSize: 10,
      includeSystemPrefixes: false
   });

   // Sync URL params to state and load files
   useEffect(() => {
      const urlSearch = getSearchFromUrl();
      const urlFileTypes = getFileFormatTypesFromUrl();
      const urlPrefix = getPrefixFromUrl();

      if (isSystemManagedPrefix(urlPrefix)) {
         updateUrlParams(undefined, undefined, "");
         return;
      }

      // Update state from URL and load files
      updateListState({
         searchValue: urlSearch,
         selectedFileTypes: urlFileTypes,
         pageIndex: 1,
         prefix: urlPrefix
      });

      loadFiles({
         pageIndex: 1,
         pageSize: listState.pageSize,
         filterString: urlSearch,
         fileTypes: urlFileTypes,
         prefix: urlPrefix
      });

      // Only run when URL params change
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [searchParams]);

   const handleTableChange = (pagination: TablePaginationConfig) => {
      const pageIndex = pagination.current || 1;
      const pageSize = pagination.pageSize || 10;
      updateListState({
         pageIndex,
         pageSize
      });
      loadFiles({
         pageIndex,
         pageSize,
         filterString: listState.searchValue,
         fileTypes: listState.selectedFileTypes,
         prefix: listState.prefix
      });
   };

   const handleUploadSuccess = () => {
      // Reload the file list after successful upload
      loadFiles({
         pageIndex: listState.pageIndex,
         pageSize: listState.pageSize,
         filterString: listState.searchValue,
         fileTypes: listState.selectedFileTypes,
         prefix: listState.prefix
      });
   };

   const handleOpenFolder = useCallback(
      (prefix: string) => {
         if (isSystemManagedPrefix(prefix)) {
            updateUrlParams(undefined, undefined, "");
            return;
         }
         setSelectedRowKeys([]);
         updateUrlParams(undefined, undefined, prefix);
      },
      [updateUrlParams]
   );

   // Handler for navigating to resource detail page
   const handleViewDetails = (resource: FileModel) => {
      if (isFolderEntry(resource)) {
         handleOpenFolder(resource.path);
         return;
      }
      if (currentProject && resource.id) {
         // Navigate to specialized detail pages
         if (resource.fileType === FileFormatType.Notebook) {
            const path = getNotebookDetailPath(currentProject, resource.id);
            navigate(path);
         } else if (resource.fileType === FileFormatType.Chart) {
            const path = getRoutePath(
               RouteNames.PROJECT_CHART_DETAIL,
               currentProject,
               {
                  fileId: resource.id,
                  fileName: resource.name
               }
            );
            navigate(path);
         } else if (resource.fileType === FileFormatType.DataTable) {
            const path = getRoutePath(
               RouteNames.PROJECT_DATA_TABLE_DETAIL,
               currentProject,
               {
                  fileId: resource.id,
                  fileName: resource.name
               }
            );
            navigate(path);
         } else {
            const path = getFileDetailPath(
               currentProject,
               resource.id,
               resource.name
            );
            navigate(path);
         }
      }
   };

   // Handler for preview button click
   const handlePreview = (resource: FileModel) => {
      setPreviewResource(resource);
      setPreviewVisible(true);
   };

   // Handler for delete button click
   const handleDelete = async (resource: FileModel) => {
      await deleteFile(resource);
   };

   const handleBulkDelete = async () => {
      if (selectedRowKeys.length === 0) {
         return;
      }

      const selectedFiles = listState.files.filter(
         (file) =>
            file.id && selectedRowKeys.includes(file.id) && !isFolderEntry(file)
      );

      if (selectedFiles.length === 0) {
         return;
      }

      setIsBulkDeleting(true);
      const result = await deleteMultipleFiles(selectedFiles);
      if (result.successCount > 0) {
         setSelectedRowKeys([]);
      }
      setIsBulkDeleting(false);
   };

   useEffect(() => {
      const currentFileIds = new Set(
         listState.files
            .map((file) => file.id)
            .filter((id): id is string => Boolean(id))
      );

      const timeoutId = window.setTimeout(() => {
         setSelectedRowKeys((prev) =>
            prev.filter((key) => currentFileIds.has(key))
         );
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [listState.files]);

   const handleSearch = (value: string) => {
      updateUrlParams(value, undefined);
   };

   const handleFileFormatTypeChange = (types: FileFormatType[]) => {
      updateUrlParams(undefined, types);
   };

   const breadcrumbItems = [
      {
         title: (
            <span
               style={{ cursor: "pointer" }}
               onClick={() => handleOpenFolder("")}
            >
               <FolderOutlined style={BREADCRUMB_ICON_STYLE} />
               Root
            </span>
         )
      },
      ...listState.prefix
         .split("/")
         .filter(Boolean)
         .map((segment, index, parts) => ({
            title: (
               <span
                  style={{ cursor: "pointer" }}
                  onClick={() =>
                     handleOpenFolder(parts.slice(0, index + 1).join("/"))
                  }
               >
                  {segment}
               </span>
            )
         }))
   ];

   // File type options for the dropdown
   const fileTypeOptions = Object.values(FileFormatType).map((type) => ({
      label: type,
      value: type
   }));

   const columns = [
      {
         title: "",
         dataIndex: "fileType",
         key: "icon",
         width: 50,
         render: (fileType: FileFormatType, record: FileModel) =>
            isFolderEntry(record) ? (
               <FolderOutlined style={FILE_ICON_STYLE} />
            ) : (
               <FileIcon fileType={fileType} />
            )
      },
      {
         title: "Name",
         dataIndex: "name",
         key: "name",
         render: (name: string, record: FileModel) => {
            return (
               <span
                  style={{ cursor: "pointer", fontWeight: 500 }}
                  onClick={() => handleViewDetails(record)}
               >
                  {isFolderEntry(record) ? `${name}/` : name}
               </span>
            );
         }
      },
      {
         title: "Owner",
         dataIndex: "ownerId",
         key: "ownerId",
         width: 100,
         render: (ownerId: string) =>
            ownerId ? (
               <UserAvatarById
                  userId={ownerId}
                  showTooltip
                  tooltipText="Owner"
               />
            ) : (
               "-"
            )
      },
      {
         title: "Type",
         dataIndex: "fileType",
         key: "fileType",
         width: 120,
         render: (fileType: FileFormatType, record: FileModel) =>
            isFolderEntry(record) ? "Folder" : fileType
      },
      {
         title: "Size",
         dataIndex: "size",
         key: "size",
         width: 100,
         render: (size: number, record: FileModel) =>
            isFolderEntry(record) ? "-" : formatFileSize(size)
      },
      {
         title: "Created",
         dataIndex: "dateCreated",
         key: "dateCreated",
         width: 120,
         render: (text: string) => (
            <Tooltip title={new Date(text).toLocaleString()}>
               {formatTimeAgo(text)}
            </Tooltip>
         )
      },
      {
         title: "Modified",
         dataIndex: "dateModified",
         key: "dateModified",
         width: 120,
         render: (text: string | null) =>
            text ? (
               <Tooltip title={new Date(text).toLocaleString()}>
                  {formatTimeAgo(text)}
               </Tooltip>
            ) : (
               "-"
            )
      },
      {
         title: "Actions",
         key: "actions",
         width: 120,
         render: (_: unknown, record: FileModel) =>
            isFolderEntry(record) ? null : (
               <FileActions
                  file={record}
                  onDownload={downloadFile}
                  onPreview={handlePreview}
                  onViewDetails={handleViewDetails}
                  onDelete={handleDelete}
                  showViewDetails={false}
                  showDelete={true}
                  usePermissions={true}
               />
            )
      }
   ];

   // Menu items for the dropdown
   const menuItems: MenuProps["items"] = [
      {
         key: "upload",
         label: "Upload Files",
         icon: <UploadOutlined />,
         onClick: () => setIsModalVisible(true)
      },
      {
         key: "notebook",
         label: "Create Notebook",
         icon: <NotebookOutlined />,
         onClick: () => setIsNotebookModalVisible(true)
      }
   ];

   return (
      <PageContainer
         key={`files-${currentProject.id}`}
         title="Files"
         description={`Browse and manage files for ${
            currentProject.projectName || "this project"
         }.`}
         routeName={RouteNames.PROJECT_FILES}
         project={currentProject}
         type="website"
         actions={
            <Space>
               <PermissionButton
                  danger
                  onClick={handleBulkDelete}
                  disabled={selectedRowKeys.length === 0 || isBulkDeleting}
                  loading={isBulkDeleting}
                  allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                  tooltipWhenDisabled="Select files to delete"
               >
                  Delete Selected
               </PermissionButton>
               <Dropdown menu={{ items: menuItems }} trigger={["click"]}>
                  <PermissionButton
                     type="primary"
                     allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                     tooltipWhenDisabled="You need contributor permissions to manage files"
                  >
                     <PlusOutlined />
                     Add <DownOutlined />
                  </PermissionButton>
               </Dropdown>
            </Space>
         }
      >
         <Flex wrap="wrap" gap="small" style={{ marginBottom: 16 }}>
            <Breadcrumb items={breadcrumbItems} />
         </Flex>

         <Flex wrap="wrap" gap="small" style={{ marginBottom: 16 }}>
            <PermissionSearch
               key={`search-${getSearchFromUrl()}`}
               placeholder="Search files"
               allowClear
               defaultValue={getSearchFromUrl()}
               onSearch={handleSearch}
               style={{ width: 200 }}
               allowedProjectRoles={[
                  ProjectRole.READER,
                  ProjectRole.OWNER,
                  ProjectRole.ADMIN,
                  ProjectRole.CONTRIBUTOR
               ]}
               requireAuthenticated
               tooltipWhenDisabled="You need to sign in to use search"
            />
            <PermissionSelect
               mode="multiple"
               allowClear
               style={{ width: 300 }}
               placeholder="Filter by file type"
               onChange={handleFileFormatTypeChange}
               value={listState.selectedFileTypes}
               options={fileTypeOptions}
               allowedProjectRoles={[
                  ProjectRole.READER,
                  ProjectRole.OWNER,
                  ProjectRole.ADMIN,
                  ProjectRole.CONTRIBUTOR
               ]}
               requireAuthenticated
               tooltipWhenDisabled="You need to sign in to use filters"
            />
         </Flex>

         <Table
            loading={listState.isLoading}
            dataSource={listState.files}
            columns={columns}
            rowKey="id"
            pagination={{
               hideOnSinglePage: true,
               current: listState.pageIndex,
               pageSize: listState.pageSize,
               total: listState.totalCount,
               showSizeChanger: true,
               pageSizeOptions: PAGE_SIZE_OPTIONS
            }}
            onChange={handleTableChange}
            scroll={{ x: 600 }}
            rowSelection={{
               selectedRowKeys,
               onChange: (keys) => setSelectedRowKeys(keys.map(String)),
               getCheckboxProps: (record) => ({
                  disabled: isFolderEntry(record)
               })
            }}
         />

         <ImagePreviewModal
            visible={previewVisible}
            resource={previewResource}
            projectId={currentProject.id}
            onClose={() => setPreviewVisible(false)}
         />

         <FileUploadModal
            visible={isModalVisible}
            onClose={() => setIsModalVisible(false)}
            onSuccess={handleUploadSuccess}
            projectId={currentProject.id}
            prefix={listState.prefix}
            configuration={currentProject.configuration}
         />

         <CreateNotebookModal
            open={isNotebookModalVisible}
            projectId={currentProject.id}
            onCancel={() => setIsNotebookModalVisible(false)}
            onCreated={(file) => {
               setIsNotebookModalVisible(false);
               if (file.id) {
                  navigate(getNotebookDetailPath(currentProject, file.id));
               }
            }}
         />

         <DownloadProgressModal
            open={downloadModalVisible}
            progress={downloadProgress ?? 0}
            fileName={downloadModalText}
            onCancel={closeDownloadModal}
         />
      </PageContainer>
   );
};

const FileListPage = () => {
   const { currentProject } = useProject();

   if (!currentProject) return null;

   return <FileListPageContent currentProject={currentProject} />;
};

export default FileListPage;
