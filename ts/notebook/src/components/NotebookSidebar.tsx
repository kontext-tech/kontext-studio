import { FileTextOutlined } from "@kontext-tech/icons";
import type { CultureInfoModel } from "@kontext-tech/schema";
import type {
   NotebookMetadata,
   SidebarTabExtension
} from "@notebook/types/notebook";
import { Form, Space, Tabs, Typography } from "antd";
import React, { useState } from "react";
import { DetailsTab, PropertiesTab } from "./tabs";

const { Text, Title } = Typography;

interface NotebookSidebarProps {
   metadata: NotebookMetadata;
   onMetadataChange?: (metadata: NotebookMetadata) => void;
   cultures?: CultureInfoModel[];
   readonly?: boolean;
   showArticleFields?: boolean;
   /** Whether to show the "Save as draft" option in article fields - defaults to true */
   showSaveAsDraft?: boolean;
   sidebarExtensions?: SidebarTabExtension[];
}

const NotebookSidebar: React.FC<NotebookSidebarProps> = ({
   metadata,
   onMetadataChange,
   cultures = [],
   readonly = false,
   showArticleFields = false,
   showSaveAsDraft = true,
   sidebarExtensions = []
}) => {
   const [form] = Form.useForm();
   const [activeTab, setActiveTab] = useState(
      sidebarExtensions.length > 0 ? sidebarExtensions[0].key : "metadata"
   );

   // Sync form values with metadata prop whenever metadata changes
   React.useEffect(() => {
      // Convert metadata to form values, including the isDraft conversion
      const formValues = {
         ...metadata,
         isDraft: !metadata.isPublished // Convert isPublished to isDraft for the form
      };
      form.setFieldsValue(formValues);
   }, [form, metadata]);

   const handleValuesChange = (
      changedValues: Partial<NotebookMetadata & { isDraft: boolean }>
   ) => {
      // Handle the isDraft to isPublished conversion
      const updatedMetadata = { ...metadata };

      Object.keys(changedValues).forEach((key) => {
         if (key === "isDraft") {
            updatedMetadata.isPublished = !changedValues.isDraft;
         } else {
            (updatedMetadata as Record<string, unknown>)[key] = (
               changedValues as Record<string, unknown>
            )[key];
         }
      });

      onMetadataChange?.(updatedMetadata);
   };

   const defaultTabs = [
      {
         key: "metadata",
         label: "Metadata",
         icon: <FileTextOutlined />,
         children: (
            <div style={{ padding: "8px 0" }}>
               <Space
                  orientation="vertical"
                  style={{ width: "100%" }}
                  size="middle"
               >
                  <div>
                     <Title level={5} style={{ margin: "0 0 8px 0" }}>
                        Notebook Metadata
                     </Title>
                     <Text type="secondary" style={{ fontSize: "12px" }}>
                        Configure properties and details for this notebook
                     </Text>
                  </div>
                  <div>
                     <PropertiesTab
                        cultures={cultures}
                        readonly={readonly}
                        showArticleFields={showArticleFields}
                        showSaveAsDraft={showSaveAsDraft}
                     />
                     <DetailsTab
                        readonly={readonly}
                        showArticleFields={showArticleFields}
                     />
                  </div>
               </Space>
            </div>
         )
      }
   ];

   const tabItems = [...sidebarExtensions, ...defaultTabs];

   // Create initial form values with proper isDraft conversion
   const initialFormValues = React.useMemo(
      () => ({
         ...metadata,
         isDraft: !metadata.isPublished
      }),
      [metadata]
   );

   return (
      <Form
         form={form}
         layout="vertical"
         initialValues={initialFormValues}
         onValuesChange={handleValuesChange}
         style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            minHeight: 0
         }}
      >
         <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            size="small"
            tabBarGutter={12}
            style={{
               flex: 1,
               display: "flex",
               flexDirection: "column",
               minHeight: 0,
               overflow: "hidden"
            }}
            styles={{
               content: {
                  height: "100%",
                  minHeight: 0,
                  overflowY: "auto",
                  paddingBottom: 20
               }
            }}
         />
      </Form>
   );
};

export default NotebookSidebar;
