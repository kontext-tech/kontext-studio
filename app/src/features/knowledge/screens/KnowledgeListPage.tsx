import PageContainer from "@/components/layout/SeoPageContainer";
import ConceptEditorModal from "@/features/knowledge/components/ConceptEditorModal";
import ConceptStatusTag from "@/features/knowledge/components/ConceptStatusTag";
import ProposalsInbox from "@/features/knowledge/components/ProposalsInbox";
import {
   useExportBundle,
   useImportBundle,
   useKnowledgeConcepts,
   useKnowledgeProposals
} from "@/features/knowledge/hooks/useKnowledge";
import {
   formatConceptDate,
   getConceptTitle
} from "@/features/knowledge/utils/conceptPresentation";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { CommonRoleGroups, PermissionButton } from "@kontext-tech/auth";
import {
   DownloadOutlined,
   PlusOutlined,
   ReloadOutlined,
   UploadOutlined
} from "@kontext-tech/icons";
import { useProject } from "@kontext-tech/project";
import type { OkfConcept } from "@kontext-tech/schema";
import { DebouncedSearch, LoadingSpinner, useUiApp } from "@kontext-tech/ui";
import {
   Alert,
   Button,
   Card,
   Empty,
   Flex,
   Space,
   Table,
   Tabs,
   Tag,
   Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type KnowledgeTab = "concepts" | "proposals";

const KnowledgeListPage = () => {
   const { currentProject } = useProject();
   const projectId = currentProject?.id;
   const navigate = useNavigate();
   const { message, modal } = useUiApp();
   const { getKnowledgeDetailPath } = useRoute();
   const fileInputRef = useRef<HTMLInputElement>(null);

   const [activeTab, setActiveTab] = useState<KnowledgeTab>("concepts");
   const [searchText, setSearchText] = useState("");
   const [editorOpen, setEditorOpen] = useState(false);
   const [editingConcept, setEditingConcept] = useState<OkfConcept | null>(
      null
   );

   const conceptsQuery = useKnowledgeConcepts(projectId);
   const proposalsQuery = useKnowledgeProposals(projectId);
   const exportBundle = useExportBundle(projectId);
   const importBundle = useImportBundle(projectId);

   const openConcept = (conceptId: string) => {
      if (!currentProject || !conceptId) {
         return;
      }
      navigate(getKnowledgeDetailPath(currentProject, conceptId));
   };

   const filteredConcepts = useMemo(() => {
      const concepts = conceptsQuery.data ?? [];
      const needle = searchText.trim().toLowerCase();
      if (!needle) {
         return concepts;
      }
      return concepts.filter((concept) =>
         [
            getConceptTitle(concept),
            concept.id,
            concept.type,
            concept.description,
            ...(concept.tags ?? [])
         ]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(needle))
      );
   }, [conceptsQuery.data, searchText]);

   const handleExport = async () => {
      try {
         await exportBundle.mutateAsync();
         message.success("OKF bundle exported");
      } catch (error) {
         message.error(
            error instanceof Error ? error.message : "Failed to export bundle"
         );
      }
   };

   const handleImportFile = async (
      event: React.ChangeEvent<HTMLInputElement>
   ) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) {
         return;
      }
      try {
         const result = await importBundle.mutateAsync(file);
         const count = result.importedConceptCount;
         message.success(`Imported ${count} concept${count === 1 ? "" : "s"}`);
         const warnings = result.conformanceWarnings ?? [];
         if (warnings.length > 0) {
            modal.warning({
               title: "Bundle imported with conformance warnings",
               content: (
                  <ul style={{ paddingLeft: 18, margin: 0 }}>
                     {warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                     ))}
                  </ul>
               )
            });
         }
      } catch (error) {
         message.error(
            error instanceof Error ? error.message : "Failed to import bundle"
         );
      }
   };

   if (!currentProject) {
      return null;
   }

   const proposalCount = proposalsQuery.data?.length ?? 0;

   const columns: ColumnsType<OkfConcept> = [
      {
         title: "Title",
         dataIndex: "title",
         key: "title",
         render: (_: unknown, record) => (
            <span
               style={{ cursor: "pointer", fontWeight: 500 }}
               onClick={() => openConcept(record.id || "")}
            >
               {getConceptTitle(record)}
            </span>
         )
      },
      {
         title: "Type",
         dataIndex: "type",
         key: "type",
         width: 140,
         render: (type: string) => <Tag>{type}</Tag>
      },
      {
         title: "Status",
         key: "status",
         width: 120,
         render: (_: unknown, record) => <ConceptStatusTag concept={record} />
      },
      {
         title: "Tags",
         dataIndex: "tags",
         key: "tags",
         render: (tags: string[]) =>
            tags?.length ? (
               <Space size={[4, 4]} wrap>
                  {tags.slice(0, 4).map((tag) => (
                     <Tag key={tag}>{tag}</Tag>
                  ))}
                  {tags.length > 4 && <Tag>+{tags.length - 4}</Tag>}
               </Space>
            ) : (
               "-"
            )
      },
      {
         title: "Last Verified",
         key: "verified",
         width: 180,
         render: (_: unknown, record) => {
            const verified = record.attestation?.verified ?? [];
            const last = verified[verified.length - 1];
            return last ? (
               <Typography.Text type="secondary">
                  {formatConceptDate(last.at)}
               </Typography.Text>
            ) : (
               "-"
            );
         }
      },
      {
         title: "Actions",
         key: "actions",
         width: 140,
         render: (_: unknown, record) => (
            <Space>
               <Button
                  size="small"
                  onClick={() => openConcept(record.id || "")}
               >
                  View
               </Button>
               <PermissionButton
                  size="small"
                  allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                  onClick={() => {
                     setEditingConcept(record);
                     setEditorOpen(true);
                  }}
               >
                  Edit
               </PermissionButton>
            </Space>
         )
      }
   ];

   const conceptsTab = conceptsQuery.isLoading ? (
      <LoadingSpinner />
   ) : conceptsQuery.isError ? (
      <Alert
         type="error"
         showIcon
         title="Failed to load knowledge concepts"
         description={
            conceptsQuery.error instanceof Error
               ? conceptsQuery.error.message
               : undefined
         }
      />
   ) : (conceptsQuery.data?.length ?? 0) === 0 ? (
      <Card>
         <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No curated knowledge yet. Create a concept or import an OKF bundle."
         >
            <PermissionButton
               type="primary"
               icon={<PlusOutlined />}
               allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
               onClick={() => {
                  setEditingConcept(null);
                  setEditorOpen(true);
               }}
            >
               Create your first concept
            </PermissionButton>
         </Empty>
      </Card>
   ) : (
      <Table
         loading={conceptsQuery.isFetching}
         dataSource={filteredConcepts}
         columns={columns}
         rowKey={(record) => record.id || getConceptTitle(record)}
         pagination={{ hideOnSinglePage: true, pageSize: 20 }}
         scroll={{ x: 720 }}
      />
   );

   return (
      <PageContainer
         key={`project-knowledge-${currentProject.id}`}
         title="Knowledge"
         description={`Curated business context for ${
            currentProject.projectName || "this project"
         }.`}
         routeName={RouteNames.PROJECT_KNOWLEDGE}
         project={currentProject}
         actions={
            <Space wrap>
               <Button
                  icon={<ReloadOutlined />}
                  loading={conceptsQuery.isFetching}
                  onClick={() => {
                     void conceptsQuery.refetch();
                     void proposalsQuery.refetch();
                  }}
               >
                  Refresh
               </Button>
               <PermissionButton
                  icon={<UploadOutlined />}
                  loading={importBundle.isPending}
                  allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                  onClick={() => fileInputRef.current?.click()}
               >
                  Import
               </PermissionButton>
               <Button
                  icon={<DownloadOutlined />}
                  loading={exportBundle.isPending}
                  onClick={() => {
                     void handleExport();
                  }}
               >
                  Export
               </Button>
               <PermissionButton
                  type="primary"
                  icon={<PlusOutlined />}
                  allowedProjectRoles={CommonRoleGroups.CONTENT_EDITORS}
                  onClick={() => {
                     setEditingConcept(null);
                     setEditorOpen(true);
                  }}
               >
                  New Concept
               </PermissionButton>
               <input
                  ref={fileInputRef}
                  type="file"
                  accept=".tar.gz,application/gzip"
                  style={{ display: "none" }}
                  onChange={(event) => {
                     void handleImportFile(event);
                  }}
               />
            </Space>
         }
         subContent={
            <Typography.Paragraph
               type="secondary"
               style={{ marginBottom: 0, maxWidth: 760 }}
            >
               Curated concepts (metric definitions, join semantics, golden
               queries) that agents reference. Agent-drafted proposals stay
               hidden until a human approves them.
            </Typography.Paragraph>
         }
      >
         <Flex vertical gap="middle">
            <DebouncedSearch
               placeholder="Filter concepts"
               allowClear
               onSearch={setSearchText}
               style={{ maxWidth: 320 }}
            />

            <Tabs
               activeKey={activeTab}
               onChange={(key) => setActiveTab(key as KnowledgeTab)}
               items={[
                  {
                     key: "concepts",
                     label: `Concepts (${conceptsQuery.data?.length ?? 0})`,
                     children: conceptsTab
                  },
                  {
                     key: "proposals",
                     label: `Proposals (${proposalCount})`,
                     children: (
                        <ProposalsInbox
                           projectId={projectId}
                           onOpenConcept={openConcept}
                        />
                     )
                  }
               ]}
            />
         </Flex>

         <ConceptEditorModal
            open={editorOpen}
            projectId={projectId}
            concept={editingConcept}
            onClose={() => setEditorOpen(false)}
         />
      </PageContainer>
   );
};

export default KnowledgeListPage;
