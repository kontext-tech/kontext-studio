const optionalStringArray = (value?: string[]) => value ?? null;

export const projectQueryKeys = {
   listing: (options: {
      searchText: string;
      pageIndex: number;
      pageSize: number;
      roleFilters?: string[];
      includePublic: boolean;
      includePrivate: boolean;
      includeDeleted: boolean;
   }) =>
      [
         "projects",
         "listing",
         {
            ...options,
            roleFilters: optionalStringArray(options.roleFilters)
         }
      ] as const
};
