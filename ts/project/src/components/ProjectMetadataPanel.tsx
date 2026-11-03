import { formatFileSize } from "@kontext-tech/common";
import {
   CheckCircleOutlined,
   ClockCircleOutlined,
   CodeOutlined,
   DatabaseOutlined,
   SettingOutlined,
   TagOutlined
} from "@kontext-tech/icons";
import type { ProjectModel } from "@kontext-tech/schema";
import { Col, Row, Space, Tag, theme, Typography } from "antd";

const { Text } = Typography;
const { useToken } = theme;

export interface ProjectMetadataPanelProps {
   project: ProjectModel;
}

export const ProjectMetadataPanel = ({
   project
}: ProjectMetadataPanelProps) => {
   const { token } = useToken();

   return (
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
         <Row gutter={[24, 16]}>
            <Col xs={24} sm={12}>
               <Space orientation="vertical" size="small">
                  <Text
                     type="secondary"
                     style={{ fontSize: "12px", textTransform: "uppercase" }}
                  >
                     Project ID
                  </Text>
                  <Text strong copyable ellipsis>
                     {project.id}
                  </Text>
               </Space>
            </Col>

            <Col xs={24} sm={12}>
               <Space orientation="vertical" size="small">
                  <Text
                     type="secondary"
                     style={{ fontSize: "12px", textTransform: "uppercase" }}
                  >
                     Project Code
                  </Text>
                  <Tag
                     icon={<CodeOutlined />}
                     color="default"
                     style={{
                        cursor: "pointer",
                        border: `1px dashed ${token.colorBorder}`,
                        borderRadius: token.borderRadiusSM
                     }}
                  >
                     <Text
                        copyable={{
                           text: project.projectCode || "",
                           tooltips: ["Copy project code", "Copied!"]
                        }}
                        style={{
                           color: token.colorTextSecondary,
                           fontFamily: "monospace",
                           margin: 0
                        }}
                     >
                        {project.projectCode}
                     </Text>
                  </Tag>
               </Space>
            </Col>
         </Row>

         <Row gutter={[24, 16]}>
            <Col xs={24} sm={12}>
               <Space orientation="vertical" size="small">
                  <Text
                     type="secondary"
                     style={{ fontSize: "12px", textTransform: "uppercase" }}
                  >
                     Created
                  </Text>
                  <Space align="center">
                     <ClockCircleOutlined
                        style={{ color: token.colorPrimary, fontSize: "16px" }}
                     />
                     <Text strong style={{ fontSize: "16px" }}>
                        {project.dateCreated
                           ? new Date(project.dateCreated).toLocaleDateString()
                           : "-"}
                     </Text>
                  </Space>
               </Space>
            </Col>

            <Col xs={24} sm={12}>
               <Space orientation="vertical" size="small">
                  <Text
                     type="secondary"
                     style={{ fontSize: "12px", textTransform: "uppercase" }}
                  >
                     Max File Size
                  </Text>
                  <Space align="center">
                     <DatabaseOutlined
                        style={{ color: token.colorPrimary, fontSize: "16px" }}
                     />
                     <Text strong style={{ fontSize: "16px" }}>
                        {formatFileSize(
                           project.configuration?.maxFileBytesSize ?? 0
                        )}
                     </Text>
                  </Space>
               </Space>
            </Col>
         </Row>

         <Row gutter={[24, 16]}>
            <Col xs={24} sm={12}>
               <Space orientation="vertical" size="small">
                  <Text
                     type="secondary"
                     style={{ fontSize: "12px", textTransform: "uppercase" }}
                  >
                     Total Storage Allocation
                  </Text>
                  <Space align="center">
                     <DatabaseOutlined
                        style={{ color: token.colorPrimary, fontSize: "16px" }}
                     />
                     <Text strong style={{ fontSize: "16px" }}>
                        {formatFileSize(
                           project.configuration?.totalStorageAllocationBytes ??
                              0
                        )}
                     </Text>
                  </Space>
               </Space>
            </Col>
         </Row>

         <div>
            <Space align="center" style={{ marginBottom: token.marginSM }}>
               <TagOutlined style={{ color: token.colorPrimary }} />
               <Text strong>Allowed File Types</Text>
            </Space>
            <div style={{ paddingLeft: token.paddingLG }}>
               {project.configuration?.allowedFileTypes ? (
                  <Space wrap>
                     {project.configuration.allowedFileTypes.map(
                        (fileType, index) => (
                           <Tag
                              key={index}
                              style={{ borderRadius: token.borderRadiusSM }}
                           >
                              {fileType.fileExtension}
                           </Tag>
                        )
                     )}
                  </Space>
               ) : (
                  <Text type="secondary">No restrictions</Text>
               )}
            </div>
         </div>

         <div>
            <Space align="center" style={{ marginBottom: token.marginSM }}>
               <SettingOutlined style={{ color: token.colorPrimary }} />
               <Text strong>Enabled Features</Text>
            </Space>
            <div style={{ paddingLeft: token.paddingLG }}>
               <Space wrap>
                  {(() => {
                     const features = project.configuration?.features;
                     return features?.length ? (
                        features.map((feature, index) => (
                           <Tag
                              key={index}
                              color="green"
                              icon={<CheckCircleOutlined />}
                              style={{ borderRadius: token.borderRadiusSM }}
                           >
                              {feature}
                           </Tag>
                        ))
                     ) : (
                        <Text type="secondary">
                           No special features enabled
                        </Text>
                     );
                  })()}
               </Space>
            </div>
         </div>
      </Space>
   );
};
