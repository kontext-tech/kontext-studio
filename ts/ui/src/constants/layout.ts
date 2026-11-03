/**
 * UI timing constants
 */
export const UI_TIMING = {
   /**
    * Delay in milliseconds to wait before executing a search after user input
    * Used for debouncing search inputs to prevent excessive API calls
    */
   SEARCH_DEBOUNCE_DELAY: 500
} as const;
