import { type ProjectModel } from "@kontext-labs/schema";
import { AccessLevelTag } from "@kontext-labs/ui";
import { Col, Flex, Row, Space, theme, Typography } from "antd";

const { Paragraph, Title } = Typography;
const { useToken } = theme;

interface ProjectInfoProps {
   project: ProjectModel;
   extra?: React.ReactNode;
}

export const ProjectInfoBanner = ({ project, extra }: ProjectInfoProps) => {
   const { token } = useToken();

   const heroStyle = {
      background: `linear-gradient(135deg, ${token.colorPrimary}1A 0%, ${token.colorInfo}1A 100%)`,
      borderRadius: token.borderRadiusLG,
      padding: token.paddingXL,
      marginBottom: token.marginXL,
      border: `1px solid ${token.colorPrimary}15`
   };

   return (
      <div style={heroStyle}>
         <Row align="middle" gutter={[24, 16]}>
            <Col xs={24} md={extra ? 16 : 24}>
               <Space orientation="vertical" size="small">
                  <Flex align="center" gap={"small"} wrap>
                     <Title
                        level={1}
                        style={{
                           margin: 0,
                           color: token.colorTextHeading
                        }}
                     >
                        {project.projectName}
                     </Title>
                     <Space>
                        <AccessLevelTag accessLevel={project.accessLevel!} />
                     </Space>
                  </Flex>
                  {project.projectDescription && (
                     <Paragraph
                        style={{
                           marginBottom: 0,
                           fontSize: "16px",
                           color: token.colorTextSecondary,
                           maxWidth: "600px"
                        }}
                     >
                        {project.projectDescription}
                     </Paragraph>
                  )}
               </Space>
            </Col>
            {extra && (
               <Col xs={24} md={8} style={{ textAlign: "right" }}>
                  {extra}
               </Col>
            )}
         </Row>
      </div>
   );
};
