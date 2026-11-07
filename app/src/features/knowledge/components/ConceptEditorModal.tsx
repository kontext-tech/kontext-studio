import { useUpsertConcept } from "@/features/knowledge/hooks/useKnowledge";
import {
   DEPRECATED_STATUS,
   DRAFT_STATUS,
   STABLE_STATUS
} from "@/features/knowledge/utils/conceptPresentation";
import type { OkfConcept } from "@kontext-tech/schema";
import { useUiApp } from "@kontext-tech/ui";
import {
   DatePicker,
   Form,
   Input,
   Modal,
   Select,
   Space,
   Typography
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect } from "react";

interface ConceptFormValues {
   id: string;
   type: string;
   title?: string;
   description?: string;
   resource?: string;
   status?: string;
   tags?: string[];
   timestamp?: Dayjs;
   staleAfter?: Dayjs;
   body?: string;
}

interface ConceptEditorModalProps {
   open: boolean;
   projectId?: string | null;
   concept?: OkfConcept | null;
   onClose: () => void;
   onSaved?: (concept: OkfConcept) => void;
}

// OKF v0.2 lifecycle vocabulary (open vocabulary; these are the recommended ones).
const STATUS_OPTIONS = [
   { label: "Draft", value: DRAFT_STATUS },
   { label: "Stable", value: STABLE_STATUS },
   { label: "Deprecated", value: DEPRECATED_STATUS }
];

const toIsoString = (value?: Dayjs): string | undefined =>
   value ? value.toISOString() : undefined;

const toDayjs = (value?: string): Dayjs | undefined =>
   value ? dayjs(value) : undefined;

const toFormValues = (
   concept?: OkfConcept | null
): Partial<ConceptFormValues> => {
   if (!concept) {
      return { type: "Metric", status: STABLE_STATUS, tags: [] };
   }
   return {
      id: concept.id,
      type: concept.type,
      title: concept.title,
      description: concept.description,
      resource: concept.resource,
      status: concept.status,
      tags: concept.tags,
      timestamp: toDayjs(concept.timestamp),
      staleAfter: toDayjs(concept.attestation?.stale_after),
      body: concept.body
   };
};

const toConcept = (
   values: ConceptFormValues,
   existing?: OkfConcept | null
): OkfConcept => ({
   ...(existing ?? {}),
   id: values.id,
   type: values.type,
   title: values.title,
   description: values.description,
   resource: values.resource,
   status: values.status,
   tags: values.tags ?? [],
   timestamp: toIsoString(values.timestamp),
   body: values.body ?? "",
   metadata: existing?.metadata ?? {},
   attestation: {
      ...(existing?.attestation ?? {}),
      verified: existing?.attestation?.verified ?? [],
      sources: existing?.attestation?.sources ?? [],
      parameters: existing?.attestation?.parameters ?? [],
      stale_after: toIsoString(values.staleAfter)
   }
});

const ConceptEditorModal = ({
   open,
   projectId,
   concept,
   onClose,
   onSaved
}: ConceptEditorModalProps) => {
   const { message } = useUiApp();
   const [form] = Form.useForm<ConceptFormValues>();
   const upsertConcept = useUpsertConcept(projectId);
   const isEditing = Boolean(concept?.id);

   useEffect(() => {
      if (open) {
         form.setFieldsValue(toFormValues(concept));
      }
   }, [open, concept, form]);

   const handleSubmit = async () => {
      let values: ConceptFormValues;
      try {
         values = await form.validateFields();
      } catch {
         return;
      }

      try {
         const saved = await upsertConcept.mutateAsync({
            conceptId: values.id,
            concept: toConcept(values, concept)
         });
         message.success(isEditing ? "Concept updated" : "Concept created");
         onSaved?.(saved);
         onClose();
      } catch (error) {
         message.error(
            error instanceof Error ? error.message : "Failed to save concept"
         );
      }
   };

   return (
      <Modal
         title={isEditing ? "Edit Concept" : "New Concept"}
         open={open}
         onCancel={onClose}
         onOk={() => {
            void handleSubmit();
         }}
         confirmLoading={upsertConcept.isPending}
         okText={isEditing ? "Save Changes" : "Create Concept"}
         width={720}
         destroyOnHidden
      >
         <Form form={form} layout="vertical">
            <Form.Item
               label="Concept ID"
               name="id"
               tooltip="Stable identity (the file path in the bundle), e.g. metrics/total-revenue"
               rules={[{ required: true, message: "Enter a concept id" }]}
            >
               <Input
                  placeholder="metrics/total-revenue"
                  disabled={isEditing}
               />
            </Form.Item>

            <Space size="middle" style={{ display: "flex" }}>
               <Form.Item
                  label="Type"
                  name="type"
                  tooltip="OKF `type` is the only required field. Use descriptive, domain-specific values."
                  style={{ flex: 1 }}
                  rules={[{ required: true, message: "Enter a type" }]}
               >
                  <Input placeholder="Metric, Table, Playbook, ..." />
               </Form.Item>
               <Form.Item
                  label="Status"
                  name="status"
                  tooltip="OKF lifecycle: draft | stable | deprecated"
                  style={{ width: 180 }}
               >
                  <Select options={STATUS_OPTIONS} />
               </Form.Item>
            </Space>

            <Form.Item label="Title" name="title">
               <Input placeholder="Human-readable title" />
            </Form.Item>

            <Form.Item label="Description" name="description">
               <Input.TextArea rows={2} />
            </Form.Item>

            <Form.Item
               label="Resource"
               name="resource"
               tooltip="Optional URI that uniquely identifies the underlying asset"
            >
               <Input placeholder="urn:kontext:table:analytics.orders" />
            </Form.Item>

            <Form.Item label="Tags" name="tags">
               <Select
                  mode="tags"
                  tokenSeparators={[","]}
                  placeholder="Add tags"
                  open={false}
                  suffixIcon={null}
               />
            </Form.Item>

            <Space size="middle" style={{ display: "flex" }}>
               <Form.Item
                  label="Timestamp"
                  name="timestamp"
                  tooltip="OKF `timestamp` — when this concept was last significantly changed"
                  style={{ flex: 1 }}
               >
                  <DatePicker showTime style={{ width: "100%" }} />
               </Form.Item>
               <Form.Item
                  label="Stale After"
                  name="staleAfter"
                  tooltip="ISO 8601 datetime after which retrieval treats this concept as stale"
                  style={{ flex: 1 }}
               >
                  <DatePicker showTime style={{ width: "100%" }} />
               </Form.Item>
            </Space>

            <Form.Item
               label="Body"
               name="body"
               tooltip="Standard markdown. Prefer the conventional headings: # Schema, # Examples, # Computation."
            >
               <Input.TextArea rows={8} />
            </Form.Item>

            <Typography.Text type="secondary">
               Tip: reference related concepts as markdown links (e.g.{" "}
               <code>[orders](/tables/orders.md)</code>) so the relationship is
               portable across OKF tools.
            </Typography.Text>
         </Form>
      </Modal>
   );
};

export default ConceptEditorModal;
