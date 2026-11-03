/// <reference types="jest" />

import {
   createErrorSegment,
   createReasoningSegment,
   createTextSegment
} from "../messageSegments";

describe("message segment factories", () => {
   it("creates a text segment with the correct shape", () => {
      expect(createTextSegment("hello", "cid-1", "parent-1")).toEqual({
         segmentType: "text",
         cid: "cid-1",
         parentId: "parent-1",
         content: "hello"
      });
   });

   it("creates a reasoning segment", () => {
      expect(createReasoningSegment("thinking")).toEqual({
         segmentType: "reasoning",
         cid: undefined,
         parentId: undefined,
         content: "thinking"
      });
   });

   it("creates an error segment", () => {
      expect(createErrorSegment("boom")).toEqual({
         segmentType: "error",
         cid: undefined,
         parentId: undefined,
         errorDetails: "boom"
      });
   });

   it("coerces null cid/parentId to undefined", () => {
      expect(createTextSegment("x", null, null)).toEqual({
         segmentType: "text",
         cid: undefined,
         parentId: undefined,
         content: "x"
      });
   });
});
