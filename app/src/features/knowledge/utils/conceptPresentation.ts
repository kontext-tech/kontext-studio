import type { OkfConcept } from "@kontext-labs/schema";

// OKF v0.2 lifecycle vocabulary. Kontext historically wrote "proposed" and
// "active"; both are still recognized when reading older bundles.
export const DRAFT_STATUS = "draft";
export const STABLE_STATUS = "stable";
export const DEPRECATED_STATUS = "deprecated";

const DRAFT_ALIASES = new Set([DRAFT_STATUS, "proposed", "pending"]);
const STABLE_ALIASES = new Set([STABLE_STATUS, "active"]);

export const getConceptTitle = (concept: OkfConcept): string =>
   concept.title || concept.id || "Untitled concept";

export const isStale = (concept: OkfConcept): boolean => {
   const staleAfter = concept.attestation?.stale_after;
   if (!staleAfter) {
      return false;
   }
   const parsed = Date.parse(staleAfter);
   return Number.isFinite(parsed) && parsed < Date.now();
};

export interface ConceptStatusPresentation {
   label: string;
   color: string;
}

export const getConceptStatus = (
   concept: OkfConcept
): ConceptStatusPresentation => {
   if (isStale(concept)) {
      return { label: "stale", color: "red" };
   }

   const status = (concept.status || "").toLowerCase();

   if (DRAFT_ALIASES.has(status)) {
      return { label: "draft", color: "gold" };
   }
   if (STABLE_ALIASES.has(status)) {
      return { label: "stable", color: "green" };
   }
   if (status === DEPRECATED_STATUS) {
      return { label: "deprecated", color: "red" };
   }
   if (status === "") {
      return { label: "untracked", color: "default" };
   }
   return { label: status, color: "blue" };
};

export const getGeneratedBy = (concept: OkfConcept): string | undefined =>
   concept.attestation?.generated?.by;

export const getVerifiedBy = (concept: OkfConcept): string[] =>
   (concept.attestation?.verified ?? []).map((entry) => entry.by);

export const formatConceptDate = (value?: string): string => {
   if (!value) {
      return "";
   }
   const parsed = Date.parse(value);
   return Number.isFinite(parsed) ? new Date(parsed).toLocaleString() : value;
};
