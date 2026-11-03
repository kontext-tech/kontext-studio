import {
   PAGE_SIZE_OPTIONS,
   type PaginatedResult,
   formatFileSize
} from "@kontext-tech/common";
import { SecureImage } from "@kontext-tech/file";
import { SearchOutlined } from "@kontext-tech/icons";
import type { FileModel } from "@kontext-tech/schema";
import {
   Button,
   Flex,
   Input,
   Modal,
   Table,
   type TablePaginationConfig
} from "antd";
import { useCallback, useEffect, useState } from "react";

export interface ImageListModalProps {
   open: boolean;
   onClose: () => void;
   onSelect: (resource: FileModel) => void;
   fetchImageResources: (
      pageIndex: number,
      pageSize: number,
      search: string
   ) => Promise<PaginatedResult<FileModel>>;
   downloadImageResource: (
      resourceId: string,
      onProgress?: (progress: number) => void
   ) => Promise<Blob | null>;
}

const ImageListModal = ({
   open,
   onClose,
   onSelect,
   fetchImageResources: fetchImageResourcesProp,
   downloadImageResource
}: ImageListModalProps) => {
   const [resources, setResources] = useState<FileModel[]>([]);
   const [isLoading, setIsLoading] = useState(false);
   const [searchValue, setSearchValue] = useState("");
   const [pageIndex, setPageIndex] = useState(1);
   const [pageSize, setPageSize] = useState(10);
   const [totalCount, setTotalCount] = useState(0);

   const fetchImageResources = useCallback(async () => {
      setIsLoading(true);
      try {
         const result = await fetchImageResourcesProp(
            pageIndex,
            pageSize,
            searchValue
         );

         // The prop is now expected to return the data directly, or throw an error on failure.
         setResources(result.items || []);
         setTotalCount(result.totalCount || 0);
      } catch (error) {
         console.error("Error in fetchImageResources:", error);
         setResources([]);
         setTotalCount(0);
      } finally {
         setIsLoading(false);
      }
   }, [fetchImageResourcesProp, pageIndex, pageSize, searchValue]);

   useEffect(() => {
      if (open) {
         const timeoutId = window.setTimeout(() => {
            void fetchImageResources();
         }, 0);

         return () => window.clearTimeout(timeoutId);
      }
   }, [open, fetchImageResources]);

   const handleTableChange = (pagination: TablePaginationConfig) => {
      setPageIndex(pagination.current || 1);
      setPageSize(pagination.pageSize || 10);
   };

   const handleSearch = (value: string) => {
      setSearchValue(value);
      setPageIndex(1); // Reset to first page on search
   };

   // Map of resourceId to { url, loading, progress }
   const handleSelectResource = (resource: FileModel) => {
      onSelect(resource);
   };

   const columns = [
      {
         title: "Preview",
         key: "preview",
         width: 100,
         render: (_: unknown, record: FileModel) => {
            if (!record.id) return null;

            return (
               <SecureImage
                  fileId={record.id}
                  downloadFn={downloadImageResource}
                  alt={record.name}
                  fallbackTitle=""
                  showError={false}
                  style={{
                     maxWidth: 50,
                     maxHeight: 50,
                     objectFit: "contain"
                  }}
               />
            );
         }
      },
      {
         title: "Name",
         dataIndex: "name",
         key: "name"
      },
      {
         title: "Size",
         dataIndex: "size",
         key: "size",
         render: (size: number) => formatFileSize(size)
      },
      {
         title: "Actions",
         key: "actions",
         render: (_: unknown, record: FileModel) => (
            <Button
               type="primary"
               size="small"
               onClick={() => handleSelectResource(record)}
            >
               Select
            </Button>
         )
      }
   ];

   return (
      <Modal
         title="Select Image"
         open={open}
         onCancel={onClose}
         footer={null}
         width={800}
      >
         <Flex vertical gap="middle">
            <Input
               placeholder="Search images"
               allowClear
               value={searchValue}
               onChange={(e) => handleSearch(e.target.value)}
               prefix={<SearchOutlined />}
            />
            <Table
               loading={isLoading}
               dataSource={resources}
               columns={columns}
               rowKey="id"
               pagination={{
                  hideOnSinglePage: true,
                  current: pageIndex,
                  pageSize: pageSize,
                  total: totalCount,
                  showSizeChanger: true,
                  pageSizeOptions: PAGE_SIZE_OPTIONS,
                  showTotal: (total) => `Total ${total} images`
               }}
               onChange={handleTableChange}
               scroll={{ y: 400 }}
            />
         </Flex>
      </Modal>
   );
};

export default ImageListModal;
