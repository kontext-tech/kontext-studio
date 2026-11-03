/**
 * Pure helpers for navigating the input message history.
 *
 * `historyIndex === -1` denotes the "live" position (past the newest entry).
 * The functions return the next index and the message to surface, allowing the
 * store to stay a thin state wrapper.
 */

export interface HistoryNavigationResult {
   index: number;
   message: string | null;
}

const HISTORY_LIMIT = 50;

export const appendHistory = (
   history: string[],
   message: string
): { messageHistory: string[]; historyIndex: number } => ({
   messageHistory: [...history, message].slice(-HISTORY_LIMIT),
   historyIndex: -1
});

export const navigateHistory = (
   history: string[],
   currentIndex: number,
   direction: "up" | "down"
): HistoryNavigationResult => {
   if (history.length === 0) {
      return { index: currentIndex, message: null };
   }

   if (direction === "up") {
      if (currentIndex === -1) {
         const index = history.length - 1;
         return { index, message: history[index] };
      }
      if (currentIndex > 0) {
         const index = currentIndex - 1;
         return { index, message: history[index] };
      }
      return { index: currentIndex, message: history[0] };
   }

   // direction === "down"
   if (currentIndex === -1) {
      return { index: currentIndex, message: null };
   }
   if (currentIndex < history.length - 1) {
      const index = currentIndex + 1;
      return { index, message: history[index] };
   }
   return { index: -1, message: "" };
};

export const getHistoryMessage = (
   history: string[],
   currentIndex: number
): string => {
   if (currentIndex === -1 || currentIndex >= history.length) {
      return "";
   }
   return history[currentIndex];
};
