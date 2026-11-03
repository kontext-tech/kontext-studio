import { K_RETURN_URL } from "../constants/queryParams";

/**
 * Creates a URL with a return URL parameter.
 */
export const createUrlWithReturnParam = (
   basePath: string,
   returnUrl: string
): string => {
   const encodedReturnUrl = encodeURIComponent(returnUrl);
   const separator = basePath.includes("?") ? "&" : "?";
   return `${basePath}${separator}${K_RETURN_URL}=${encodedReturnUrl}`;
};
