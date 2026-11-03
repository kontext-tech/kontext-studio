/// <reference types="jest" />

import type { Artifact } from "@kontext-labs/schema";
import { reduceArtifactRemoval } from "../artifactActions";

const artifact = (artifactId: string, updatedAt: string): Artifact =>
   ({
      id: `record-${artifactId}`,
      sessionId: "session-1",
      artifactId,
      artifactType: "notebook",
      title: artifactId,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt,
      meta: null
   }) as unknown as Artifact;

describe("reduceArtifactRemoval", () => {
   const baseState = {
      artifacts: [
         artifact("a", "2026-01-01T00:00:00Z"),
         artifact("b", "2026-01-02T00:00:00Z")
      ],
      artifactRuntimeById: { a: {}, b: {} } as never,
      activeArtifactId: "b"
   };

   it("removes a non-active artifact without changing active selection", () => {
      const next = reduceArtifactRemoval(baseState, "a");
      expect(next.artifacts.map((x) => x.artifactId)).toEqual(["b"]);
      expect(next.activeArtifactId).toBe("b");
      expect(Object.keys(next.artifactRuntimeById)).toEqual(["b"]);
   });

   it("promotes the most recent remaining artifact when active is removed", () => {
      const next = reduceArtifactRemoval(baseState, "b");
      expect(next.activeArtifactId).toBe("a");
      expect(Object.keys(next.artifactRuntimeById)).toEqual(["a"]);
   });

   it("clears active selection when the last artifact is removed", () => {
      const single = {
         artifacts: [artifact("only", "2026-01-01T00:00:00Z")],
         artifactRuntimeById: { only: {} } as never,
         activeArtifactId: "only"
      };
      const next = reduceArtifactRemoval(single, "only");
      expect(next.artifacts).toEqual([]);
      expect(next.activeArtifactId).toBeNull();
      expect(next.artifactRuntimeById).toEqual({});
   });
});
