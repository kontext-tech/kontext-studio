export const getPlatformBaseUrl = () =>
   window.ENV?.PUBLIC_KONTEXT_URL || window.location.origin;

export const getPlatformVersion = () => window.ENV?.VERSION || "v0.0.0";
