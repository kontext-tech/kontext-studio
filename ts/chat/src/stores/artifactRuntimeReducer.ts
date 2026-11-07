import type {
   Artifact,
   ArtifactAction,
   ArtifactEventData
} from "@kontext-tech/schema";
import { ArtifactType } from "@kontext-tech/schema";

export interface ArtifactRuntimeEntry {
   artifactId: string;
   artifactType: ArtifactType;
   pendingActions: ArtifactAction[];
   lastSequence?: number;
   refreshToken: number;
   seenActionKeys: Record<string, true>;
}

export interface ArtifactRuntimeReducerState {
   artifacts: Artifact[];
   artifactRuntimeById: Record<string, ArtifactRuntimeEntry>;
   activeArtifactId: string | null;
   isSidebarOpen: boolean;
}

const getActionKey = (action: ArtifactAction): string =>
   `${action.actionType}:${action.sequence}:${JSON.stringify(action.payload)}`;

/**
 * Upper bound on the per-artifact live action log. The log exists so a viewer
 * mounting mid-stream can replay recent mutations without a full reload; the
 * server document is authoritative and viewers reconcile on every refresh
 * token, so retaining a long tail is unnecessary. Mirrors the notebook store's
 * `MAX_APPLIED_SEQUENCES` bound to keep long sessions from growing without
 * limit.
 */
const MAX_RETAINED_ACTIONS = 2000;

const getLastSequence = (
   actions: ArtifactAction[] | undefined
): number | undefined =>
   actions && actions.length > 0
      ? actions.reduce(
           (max, action) => Math.max(max, action.sequence),
           actions[0].sequence
        )
      : undefined;

export function reduceArtifactEvent(
   state: ArtifactRuntimeReducerState,
   eventData: ArtifactEventData
): ArtifactRuntimeReducerState {
   const artifact = eventData.artifact;
   const existingArtifactIndex = state.artifacts.findIndex(
      (entry) => entry.artifactId === artifact.artifactId
   );
   const nextArtifacts = [...state.artifacts];

   if (existingArtifactIndex === -1) {
      nextArtifacts.push(artifact);
   } else {
      nextArtifacts[existingArtifactIndex] = artifact;
   }

   const existingRuntime = state.artifactRuntimeById[artifact.artifactId];
   const nextActions: ArtifactAction[] = [];
   const seenActionKeys = { ...(existingRuntime?.seenActionKeys ?? {}) };

   for (const action of eventData.actions ?? []) {
      const actionKey = getActionKey(action);
      if (seenActionKeys[actionKey]) {
         continue;
      }
      seenActionKeys[actionKey] = true;
      nextActions.push(action);
   }

   const lastSequence = getLastSequence(nextActions);
   // Every artifact update advances the refresh token. Viewers use it as a
   // signal to reconcile with the authoritative server state (charts re-fetch
   // their document, notebooks reconcile missed/partial live replays).
   const refreshToken = (existingRuntime?.refreshToken ?? 0) + 1;

   // Merge and bound the live action log, pruning the oldest actions (and
   // their dedupe keys) so memory stays flat across long streaming sessions.
   const mergedActions = [
      ...(existingRuntime?.pendingActions ?? []),
      ...nextActions
   ];
   let pendingActions = mergedActions;
   if (mergedActions.length > MAX_RETAINED_ACTIONS) {
      const overflow = mergedActions.length - MAX_RETAINED_ACTIONS;
      for (let i = 0; i < overflow; i += 1) {
         delete seenActionKeys[getActionKey(mergedActions[i])];
      }
      pendingActions = mergedActions.slice(overflow);
   }

   // Steal focus only when the artifact is brand new. Updates to already
   // visible artifacts stay in their tabs; bounce-stealing focus would
   // destroy hidden tabs (destroyOnHidden) and remount their viewers -
   // charts visibly refresh even when unrelated artifacts are updated.
   const isNewArtifact = existingArtifactIndex === -1;

   return {
      artifacts: nextArtifacts,
      artifactRuntimeById: {
         ...state.artifactRuntimeById,
         [artifact.artifactId]: {
            artifactId: artifact.artifactId,
            artifactType: artifact.artifactType as ArtifactType,
            pendingActions,
            lastSequence:
               Math.max(
                  lastSequence ?? 0,
                  existingRuntime?.lastSequence ?? 0
               ) || undefined,
            refreshToken,
            seenActionKeys
         }
      },
      activeArtifactId: isNewArtifact
         ? artifact.artifactId
         : state.activeArtifactId,
      isSidebarOpen: isNewArtifact ? true : state.isSidebarOpen
   };
}
