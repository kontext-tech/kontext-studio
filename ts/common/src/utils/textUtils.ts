/**
 * Normalizes a tag by trimming whitespace and converting to lowercase
 * @param tag The tag to normalize
 * @returns A normalized tag
 */
export const normalizeTag = (tag: string): string => {
   return tag.trim().toLowerCase();
};

/**
 * Validates if a tag contains only letters, numbers, spaces, and dashes
 * @param tag The tag to validate
 * @returns boolean indicating if the tag format is valid
 */
export const validateTagFormat = (tag: string): boolean => {
   const tagRegex = /^[a-zA-Z0-9\s-]+$/;
   return tagRegex.test(tag);
};
