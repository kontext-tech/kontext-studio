import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import type { ProjectNavModel, ProjectModel } from "@kontext-labs/schema";

/**
 * Hook that returns a function to generate canonical URLs using the routing system
 * instead of relying on window.location.href
 *
 * @returns A function that generates canonical URLs based on route configuration
 */
const useCanonicalUrl = () => {
   const { getRoutePath, getGeneralRoutePath } = useRoute();

   /**
    * Generates a canonical URL for the specified route
    *
    * @param routeName The name of the route
    * @param project Optional project for project-specific routes
    * @returns A fully qualified canonical URL
    */
   const getCanonicalUrl = (
      routeName: RouteNames,
      project?: ProjectNavModel | ProjectModel | null
   ): string => {
      const baseUrl = window.location.origin;

      if (project) {
         // For routes with parameters
         return `${baseUrl}${getRoutePath(routeName, project)}`;
      } else {
         // For general routes without parameters
         return `${baseUrl}${getGeneralRoutePath(routeName)}`;
      }
   };

   return getCanonicalUrl;
};

export default useCanonicalUrl;
