import { EditOutlined } from "@kontext-tech/icons";
import { Button, Flex, Input, Typography, theme } from "antd";
import React, { type ReactNode, useState } from "react";

const { Title } = Typography;
const { useToken } = theme;

export interface PageHeaderBaseProps {
   title: string;
   actions?: ReactNode;
   subContent?: ReactNode;
   variant?: "document" | "application";
   onSaveTitle?: (newTitle: string) => Promise<void> | void;
   isSaving?: boolean;
   isTitleEditable?: boolean;
   breadcrumb?: ReactNode;
}

const PageHeaderBase: React.FC<PageHeaderBaseProps> = ({
   title,
   actions,
   subContent,
   variant = "document",
   onSaveTitle,
   isSaving = false,
   isTitleEditable = false,
   breadcrumb
}) => {
   const { token } = useToken();
   const [isEditing, setIsEditing] = useState(false);
   const [localTitle, setLocalTitle] = useState(title);

   const handleCancel = () => {
      setLocalTitle(title);
      setIsEditing(false);
   };

   const handleSave = async () => {
      const trimmed = localTitle.trim();
      if (!trimmed || trimmed === title) {
         setIsEditing(false);
         setLocalTitle(title);
         return;
      }

      if (onSaveTitle) {
         try {
            await onSaveTitle(trimmed);
         } catch (e) {
            console.error("Failed to save title", e);
         }
      }
      setIsEditing(false);
   };

   if (variant === "application") {
      return (
         <div
            style={{
               borderBottom: `1px solid ${token.colorBorderSecondary}`,
               background: token.colorBgContainer,
               display: "flex",
               flexDirection: "column",
               flexShrink: 0
            }}
         >
            <Flex
               align="center"
               justify="space-between"
               style={{
                  width: "100%",
                  minHeight: "var(--app-chrome-row-height, 56px)",
                  padding: "0 var(--app-page-content-padding, 24px)"
               }}
            >
               <Flex
                  align="center"
                  gap="small"
                  style={{ flex: 1, minWidth: 0 }}
               >
                  {isEditing ? (
                     <Flex align="center" gap="small" style={{ width: "100%" }}>
                        <Input
                           value={localTitle}
                           onChange={(e) => setLocalTitle(e.target.value)}
                           onPressEnter={handleSave}
                           size="small"
                           style={{ width: "100%", maxWidth: 400 }}
                           autoFocus
                           disabled={isSaving}
                        />
                        <Button
                           type="primary"
                           size="small"
                           onClick={handleSave}
                           loading={isSaving}
                        >
                           Save
                        </Button>
                        <Button
                           size="small"
                           onClick={handleCancel}
                           disabled={isSaving}
                        >
                           Cancel
                        </Button>
                     </Flex>
                  ) : (
                     <Flex vertical style={{ minWidth: 0, flex: 1 }} gap={0}>
                        {breadcrumb}
                        <Flex align="center" gap="x-small">
                           <Title
                              level={5}
                              style={{
                                 margin: 0
                              }}
                              ellipsis={{ tooltip: title }}
                           >
                              {title}
                           </Title>
                           {isTitleEditable && onSaveTitle && (
                              <Button
                                 type="text"
                                 size="small"
                                 icon={<EditOutlined />}
                                 onClick={() => setIsEditing(true)}
                                 style={{ flexShrink: 0 }}
                              />
                           )}
                        </Flex>
                     </Flex>
                  )}
               </Flex>

               {actions && (
                  <Flex align="center" gap="small" style={{ flexShrink: 0 }}>
                     {actions}
                  </Flex>
               )}
            </Flex>
            {subContent && (
               <div
                  style={{
                     padding: "0 var(--app-page-content-padding, 24px) 12px"
                  }}
               >
                  {subContent}
               </div>
            )}
         </div>
      );
   }

   return (
      <div style={{ marginBottom: "24px" }}>
         {breadcrumb}
         <Flex justify="space-between" align="center" wrap="wrap" gap="small">
            <Typography.Title level={1} style={{ margin: 0 }}>
               {title}
            </Typography.Title>
            {actions && <Flex gap="small">{actions}</Flex>}
         </Flex>
         {subContent && <div style={{ marginTop: "12px" }}>{subContent}</div>}
      </div>
   );
};

export default PageHeaderBase;
