export function getUserDisplayName(user: {
   firstName?: string | null;
   lastName?: string | null;
}): string {
   return [user.firstName, user.lastName].filter(Boolean).join(" ") || "User";
}
