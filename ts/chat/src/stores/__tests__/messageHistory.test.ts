/// <reference types="jest" />

import {
   appendHistory,
   getHistoryMessage,
   navigateHistory
} from "../messageHistory";

describe("appendHistory", () => {
   it("appends a message and resets the index to -1", () => {
      expect(appendHistory(["a"], "b")).toEqual({
         messageHistory: ["a", "b"],
         historyIndex: -1
      });
   });

   it("keeps only the last 50 messages", () => {
      const history = Array.from({ length: 50 }, (_, i) => `m${i}`);
      const { messageHistory } = appendHistory(history, "newest");
      expect(messageHistory).toHaveLength(50);
      expect(messageHistory[0]).toBe("m1");
      expect(messageHistory[49]).toBe("newest");
   });
});

describe("navigateHistory", () => {
   const history = ["oldest", "middle", "newest"];

   it("returns null for empty history", () => {
      expect(navigateHistory([], -1, "up").message).toBeNull();
   });

   it("navigates up from live position to newest", () => {
      expect(navigateHistory(history, -1, "up")).toEqual({
         index: 2,
         message: "newest"
      });
   });

   it("navigates up through older messages", () => {
      expect(navigateHistory(history, 2, "up")).toEqual({
         index: 1,
         message: "middle"
      });
      expect(navigateHistory(history, 1, "up")).toEqual({
         index: 0,
         message: "oldest"
      });
   });

   it("stays at the beginning when navigating up past oldest", () => {
      expect(navigateHistory(history, 0, "up")).toEqual({
         index: 0,
         message: "oldest"
      });
   });

   it("navigates down toward newer messages", () => {
      expect(navigateHistory(history, 0, "down")).toEqual({
         index: 1,
         message: "middle"
      });
   });

   it("returns to live position after navigating down past newest", () => {
      expect(navigateHistory(history, 2, "down")).toEqual({
         index: -1,
         message: ""
      });
   });

   it("returns null when navigating down from live position", () => {
      expect(navigateHistory(history, -1, "down").message).toBeNull();
   });
});

describe("getHistoryMessage", () => {
   it("returns empty string for live position", () => {
      expect(getHistoryMessage(["a", "b"], -1)).toBe("");
   });

   it("returns empty string for out-of-range index", () => {
      expect(getHistoryMessage(["a"], 5)).toBe("");
   });

   it("returns the message at the given index", () => {
      expect(getHistoryMessage(["a", "b", "c"], 1)).toBe("b");
   });
});
