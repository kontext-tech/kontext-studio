import PageContainer from "@/components/layout/SeoPageContainer";
import ConceptEditorModal from "@/features/knowledge/components/ConceptEditorModal";
import ConceptStatusTag from "@/features/knowledge/components/ConceptStatusTag";
import {
   useDeleteConcept,
   useKnowledgeConcept
} from "@/features/knowledge/hooks/useKnowledge";
import {
   formatConceptDate,
   getConceptTitle,
   getGeneratedBy,
   getVerifiedBy
} from "@/features/knowledge/utils/conceptPresentation";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { CommonRoleGroups, PermissionButton } from "@kontext-labs/auth";
import { DeleteOutlined, EditOutlined } from "@kontext-labs/icons";
import { useProject } from "@kontext-labs/project";
import { MarkdownRenderer } from "@kontext-labs/chat";
import { LoadingSpinner, useUiApp } from "@kontext-labs/ui";
import {
   Alert,
   Card,
   Descriptions,
   Divider,
   Empty,
   Flex,
   Space,
   Tag,
   Typography
} from "antd";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const KnowledgeDetailPage = () => {
   const params = useParams<{ "*": string }>();
   const conceptId = params["*"];
   const { currentProject } = useProject();
   const projectId = currentProject?.id;
   const navigate = useNavigate();
   const { message, modal } = useUiApp();
   const { getKnowledgePath } = useRoute();

   const [editorOpen, setEditorOpen] = useState(false);
   const conceptQuery = useKnowledgeConcept(projectId, conceptId);
   const deleteConcept = useDeleteConcept(projectId);

   const handleDelete = (conceptIdToDelete: string, title: string) => {
      modal.confirm({
         title: `Delete "${title}"?`,
         content:
            "This removes the concept from the durable OKF store and its knowledge-index projection.",
         okText: "Delete",
         okButtonProps: { danger: true },
         onOk: async () => {
            try {
               await deleteConcept.mutateAsync(conceptIdToDelete);
               message.success("Concept deleted");
               navigate(getKnowledgePath(currentProject));
            } catch (error) {
               message.error(
                  error instanceof Error
                     ? error.message
                     : "Failed to delete concept"
               );
            }
         }
      });
   };

   if (!currentProject) {
      return null;
   }

   const concept = conceptQuery.data;

   return (
      <PageContainer
         title={concept ? getConceptTitle(concept) : "Knowledge Concept"}
         description="Curated knowledge concept."
         routeName={RouteNames.PROJECT_KNOWLEDGE_DETAIL}
         project={currentProject}
         actions={
            concept ? (
               <Space>
                  <PermissionButton
                     icon={<EditOutlined />}
                     allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                     onClick={() => setEditorOpen(true)}
                  >
                     Edit
                  </PermissionButton>
                  <PermissionButton
                     danger
                     icon={<DeleteOutlined />}
                     loading={deleteConcept.isPending}
                     allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                     onClick={() =>
                        handleDelete(concept.id || "", getConceptTitle(concept))
                     }
                  >
                     Delete
                  </PermissionButton>
               </Space>
            ) : undefined
         }
      >
         {conceptQuery.isLoading ? (
            <LoadingSpinner />
         ) : conceptQuery.isError ? (
            <Alert
               type="error"
               showIcon
               title="Failed to load concept"
               description={
                  conceptQuery.error instanceof Error
                     ? conceptQuery.error.message
                     : undefined
               }
            />
         ) : !concept ? (
            <Card>
               <Empty description="This concept could not be found." />
            </Card>
         ) : (
            <Flex vertical gap="middle">
               <Space wrap>
                  <Tag>{concept.type}</Tag>
                  <ConceptStatusTag concept={concept} />
                  {(concept.tags ?? []).map((tag) => (
                     <Tag key={tag}>{tag}</Tag>
                  ))}
               </Space>

               {concept.description && (
                  <Typography.Paragraph>
                     {concept.description}
                  </Typography.Paragraph>
               )}

               <Card title="Body">
                  {concept.body ? (
                     <MarkdownRenderer content={concept.body} />
                  ) : (
                     <Typography.Text type="secondary">
                        No body content.
                     </Typography.Text>
                  )}
               </Card>

               <Card title="Attestation">
                  <Descriptions column={1} size="small" bordered>
                     <Descriptions.Item label="Resource">
                        {concept.resource || "-"}
                     </Descriptions.Item>
                     <Descriptions.Item label="Generated By">
                        {getGeneratedBy(concept) || "-"}
                     </Descriptions.Item>
                     <Descriptions.Item label="Generated At">
                        {formatConceptDate(
                           concept.attestation?.generated?.at
                        ) || "-"}
                     </Descriptions.Item>
                     <Descriptions.Item label="Verified By">
                        {getVerifiedBy(concept).length > 0
                           ? getVerifiedBy(concept).join(", ")
                           : "-"}
                     </Descriptions.Item>
                     <Descriptions.Item label="Stale After">
                        {concept.attestation?.stale_after || "-"}
                     </Descriptions.Item>
                  </Descriptions>
               </Card>

               <Divider style={{ margin: 0 }} />
               <Typography.Text type="secondary">
                  Concept ID:{" "}
                  <Typography.Text code>{concept.id}</Typography.Text>
               </Typography.Text>
            </Flex>
         )}

         <ConceptEditorModal
            open={editorOpen}
            projectId={projectId}
            concept={concept ?? null}
            onClose={() => setEditorOpen(false)}
            onSaved={() => {
               void conceptQuery.refetch();
            }}
         />
      </PageContainer>
   );
};

export default KnowledgeDetailPage;
