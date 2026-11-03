import { Flex, Space, Typography } from "antd";
import React, { type ReactNode } from "react";

export interface PageContainerProps {
   title?: string;
   subTitle?: string;
   description?: string;
   actions?: ReactNode;
   subContent?: ReactNode;
   showPageTitle?: boolean;
   fluid?: boolean;
   contentMaxWidth?: number | string;
   style?: React.CSSProperties;
   gap?: string | number;
   topContent?: ReactNode;
   header?: ReactNode;
   children: ReactNode;
}

const PageContainer = ({
   title,
   subTitle,
   description,
   actions,
   subContent,
   showPageTitle = true,
   fluid = false,
   contentMaxWidth,
   style,
   gap = "middle",
   topContent,
   header,
   children
}: PageContainerProps) => {
   const content = fluid ? (
      children
   ) : (
      <Space orientation="vertical" style={{ width: "100%" }}>
         {children}
      </Space>
   );

   const defaultHeader = title ? (
      <Flex align="flex-start" justify="space-between" gap="middle" wrap>
         <Flex vertical gap={subTitle || description ? 4 : 0}>
            <Typography.Title level={2} style={{ margin: 0 }}>
               {title}
            </Typography.Title>
            {subTitle && (
               <Typography.Text type="secondary">{subTitle}</Typography.Text>
            )}
            {description && (
               <Typography.Paragraph
                  type="secondary"
                  style={{ marginBottom: 0 }}
               >
                  {description}
               </Typography.Paragraph>
            )}
         </Flex>
         {actions && <div>{actions}</div>}
      </Flex>
   ) : null;

   const containerContent = (
      <>
         {topContent}

         {showPageTitle ? header || defaultHeader : null}

         {!showPageTitle && actions && (
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
               {actions}
            </div>
         )}

         {subContent && <div>{subContent}</div>}
         <div style={{ flex: 1, minHeight: 0 }}>{content}</div>
      </>
   );

   return (
      <Flex
         vertical
         gap={contentMaxWidth ? 0 : fluid ? 0 : gap}
         style={{ ...style, flex: 1, minHeight: 0 }}
      >
         {contentMaxWidth ? (
            <Flex
               vertical
               gap={fluid ? 0 : gap}
               style={{
                  width: "100%",
                  maxWidth: contentMaxWidth,
                  margin: "0 auto",
                  flex: 1,
                  minHeight: 0
               }}
            >
               {containerContent}
            </Flex>
         ) : (
            containerContent
         )}
      </Flex>
   );
};

export default PageContainer;
