/// <reference types="jest" />

import {
   ArtifactEventKind,
   ArtifactType,
   type ArtifactEventData
} from "@kontext-labs/schema";
import {
   type ArtifactRuntimeReducerState,
   reduceArtifactEvent
} from "../artifactRuntimeReducer";

const baseState: ArtifactRuntimeReducerState = {
   artifacts: [],
   artifactRuntimeById: {},
   activeArtifactId: null,
   isSidebarOpen: false
};

describe("reduceArtifactEvent", () => {
   it("adds durable artifacts and notebook runtime actions", () => {
      const eventData: ArtifactEventData = {
         kind: ArtifactEventKind.created,
         artifact: {
            id: "record-1",
            sessionId: "session-1",
            artifactId: "artifact-1",
            artifactType: ArtifactType.Notebook,
            title: "Notebook",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            meta: null
         },
         actions: [
            {
               actionType: "updateMetadata",
               sequence: 1,
               payload: {
                  varField: "title",
                  value: "Notebook"
               }
            }
         ],
         sourceToolCallId: "tool-1"
      };

      const reduced = reduceArtifactEvent(baseState, eventData);

      expect(reduced.artifacts).toHaveLength(1);
      expect(reduced.activeArtifactId).toBe("artifact-1");
      expect(reduced.isSidebarOpen).toBe(true);
      expect(
         reduced.artifactRuntimeById["artifact-1"]?.pendingActions
      ).toHaveLength(1);
   });

   it("bumps chart refresh tokens without duplicating actions", () => {
      const eventData: ArtifactEventData = {
         kind: ArtifactEventKind.updated,
         artifact: {
            id: "record-2",
            sessionId: "session-1",
            artifactId: "chart-1",
            artifactType: ArtifactType.Chart,
            title: "Chart",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            meta: null
         },
         actions: [
            {
               actionType: "setChartData",
               sequence: 2,
               payload: {
                  dataId: "data-1"
               }
            }
         ],
         sourceToolCallId: "tool-2"
      };

      const first = reduceArtifactEvent(baseState, eventData);
      const second = reduceArtifactEvent(first, eventData);

      expect(second.artifactRuntimeById["chart-1"]?.refreshToken).toBe(2);
      expect(
         second.artifactRuntimeById["chart-1"]?.pendingActions
      ).toHaveLength(1);
   });

   it("advances the refresh token for notebook updates so views can reconcile", () => {
      const eventData: ArtifactEventData = {
         kind: ArtifactEventKind.updated,
         artifact: {
            id: "record-3",
            sessionId: "session-1",
            artifactId: "notebook-1",
            artifactType: ArtifactType.Notebook,
            title: "Notebook",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            meta: null
         },
         actions: [
            {
               actionType: "upsertBlock",
               sequence: 3,
               payload: {
                  cid: "block-1",
                  blockType: "paragraph",
                  data: { content: "hi" }
               }
            }
         ],
         sourceToolCallId: "tool-3"
      };

      const first = reduceArtifactEvent(baseState, eventData);
      const second = reduceArtifactEvent(first, eventData);

      expect(second.artifactRuntimeById["notebook-1"]?.refreshToken).toBe(2);
      expect(
         second.artifactRuntimeById["notebook-1"]?.pendingActions
      ).toHaveLength(1);
   });

   it("does not steal focus for updates to artifacts that already exist", () => {
      const eventData: ArtifactEventData = {
         kind: ArtifactEventKind.updated,
         artifact: {
            id: "record-4",
            sessionId: "session-1",
            artifactId: "chart-2",
            artifactType: ArtifactType.Chart,
            title: "Chart",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            meta: null
         },
         actions: [
            {
               actionType: "setChartData",
               sequence: 4,
               payload: {
                  dataId: "data-2"
               }
            }
         ],
         sourceToolCallId: "tool-4"
      };

      const createdState = {
         ...baseState,
         artifacts: [eventData.artifact],
         artifactRuntimeById: {},
         activeArtifactId: "other-artifact",
         isSidebarOpen: false
      };

      const reduced = reduceArtifactEvent(createdState, eventData);

      expect(reduced.activeArtifactId).toBe("other-artifact");
      expect(reduced.isSidebarOpen).toBe(false);
      expect(reduced.artifactRuntimeById["chart-2"]?.refreshToken).toBe(1);
   });

   it("bounds the retained live action log for long sessions", () => {
      const makeActions = (start: number, count: number) =>
         Array.from({ length: count }, (_, offset) => ({
            actionType: "upsertBlock" as const,
            sequence: start + offset,
            payload: {
               cid: `block-${start + offset}`,
               blockType: "paragraph",
               data: { content: "x" }
            }
         }));

      let state: ArtifactRuntimeReducerState = baseState;
      let sequence = 0;
      for (let batch = 0; batch < 60; batch += 1) {
         state = reduceArtifactEvent(state, {
            kind: ArtifactEventKind.updated,
            artifact: {
               id: "record-bound",
               sessionId: "session-1",
               artifactId: "notebook-bound",
               artifactType: ArtifactType.Notebook,
               title: "Notebook",
               createdAt: "2026-01-01T00:00:00Z",
               updatedAt: "2026-01-01T00:00:00Z",
               meta: null
            },
            actions: makeActions(sequence, 50),
            sourceToolCallId: `tool-${batch}`
         });
         sequence += 50;
      }

      const runtime = state.artifactRuntimeById["notebook-bound"];
      expect(runtime?.pendingActions.length).toBe(2000);
      // Dedupe keys stay in lockstep with the retained log.
      expect(Object.keys(runtime?.seenActionKeys ?? {})).toHaveLength(2000);
      // The newest actions are the ones kept.
      expect(runtime?.pendingActions[1999]?.sequence).toBe(2999);
   });
});
