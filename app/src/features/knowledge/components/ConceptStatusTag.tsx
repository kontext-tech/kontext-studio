import { getConceptStatus } from "@/features/knowledge/utils/conceptPresentation";
import type { OkfConcept } from "@kontext-tech/schema";
import { Tag } from "antd";

interface ConceptStatusTagProps {
   concept: OkfConcept;
}

const ConceptStatusTag = ({ concept }: ConceptStatusTagProps) => {
   const status = getConceptStatus(concept);
   return <Tag color={status.color}>{status.label}</Tag>;
};

export default ConceptStatusTag;
