import type { Artifact } from "@kontext-labs/schema";
import type { ArtifactRuntimeEntry } from "./artifactRuntimeReducer";

interface ArtifactRemovalState {
   artifacts: Artifact[];
   artifactRuntimeById: Record<string, ArtifactRuntimeEntry>;
   activeArtifactId: string | null;
}

const artifactTimestamp = (artifact: Artifact): number =>
   (artifact.updatedAt ? new Date(artifact.updatedAt).getTime() : 0) ||
   new Date(artifact.createdAt).getTime();

/**
 * Compute the next artifact-related slice of state after removing an artifact.
 * When the removed artifact was active, the most recently updated remaining
 * artifact is promoted (or the active selection is cleared when none remain).
 */
export const reduceArtifactRemoval = (
   state: ArtifactRemovalState,
   artifactId: string
): ArtifactRemovalState => {
   const remainingArtifacts = state.artifacts.filter(
      (artifact) => artifact.artifactId !== artifactId
   );

   let newActiveArtifactId = state.activeArtifactId;
   if (state.activeArtifactId === artifactId) {
      if (remainingArtifacts.length > 0) {
         const latestArtifact = remainingArtifacts.reduce((latest, current) =>
            artifactTimestamp(current) > artifactTimestamp(latest)
               ? current
               : latest
         );
         newActiveArtifactId = latestArtifact.artifactId;
      } else {
         newActiveArtifactId = null;
      }
   }

   return {
      artifacts: remainingArtifacts,
      artifactRuntimeById: Object.fromEntries(
         Object.entries(state.artifactRuntimeById).filter(
            ([currentArtifactId]) => currentArtifactId !== artifactId
         )
      ),
      activeArtifactId: newActiveArtifactId
   };
};
