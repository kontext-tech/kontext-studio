import { formatNumber } from "../formatUtils";

describe("formatNumber", () => {
   it("formats numbers correctly", () => {
      expect(formatNumber(0, "short")).toBe("0");
      expect(formatNumber(100, "short")).toBe("100");
      expect(formatNumber(999, "short")).toBe("999");
      expect(formatNumber(1000, "short")).toBe("1K");
      expect(formatNumber(1500, "short")).toBe("1.5K");
      expect(formatNumber(1000000, "short")).toBe("1M");
      expect(formatNumber(1500000, "short")).toBe("1.5M");
      expect(formatNumber(1000000000, "short")).toBe("1B");
      expect(formatNumber(1500000000, "short")).toBe("1.5B");
      expect(formatNumber(1000000000000, "short")).toBe("1T");
   });

   it("handles negative numbers", () => {
      expect(formatNumber(-1000, "short")).toBe("-1K");
      expect(formatNumber(-1500000, "short")).toBe("-1.5M");
   });

   it("handles custom digits", () => {
      expect(formatNumber(1500, "short", 2)).toBe("1.5K"); // 1.50 -> 1.5
      expect(formatNumber(1234, "short", 2)).toBe("1.23K");
   });

   it("handles string inputs", () => {
      expect(formatNumber("1000", "short")).toBe("1K");
      expect(formatNumber("abc")).toBe("abc");
   });

   it("defaults to short", () => {
      expect(formatNumber(1000)).toBe("1K");
      expect(formatNumber(1500)).toBe("1.5K");
      expect(formatNumber(1000000)).toBe("1M");
   });

   it("handles explicit formats", () => {
      expect(formatNumber(1234, "thousands")).toBe("1.2K");
      expect(formatNumber(1234567, "millions")).toBe("1.2M");
      expect(formatNumber(1234567890, "billions")).toBe("1.2B");
      expect(formatNumber(1234, "none")).toBe("1,234");
   });
});
