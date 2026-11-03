import { useRoute } from "@/hooks/useRoute";
import { routeRegistry } from "@/routing";
import { RouteNames } from "@/types";
import { ProjectOutlined } from "@kontext-labs/icons";
import type { ProjectModel, ProjectNavModel } from "@kontext-labs/schema";
import { Breadcrumb } from "antd";
import React from "react";
import { Link } from "react-router-dom";

interface BreadcrumbNavProps {
   /**
    * Current route name
    */
   routeName: RouteNames;

   /**
    * Optional project for project-specific routes
    */
   project?: ProjectNavModel | ProjectModel | null;
}

/**
 * Component that dynamically generates breadcrumb navigation
 * based on the current route and its parent hierarchy.
 */
const BreadcrumbNav: React.FC<BreadcrumbNavProps> = ({
   routeName,
   project
}) => {
   const { getProjectHomePath } = useRoute();
   const context = { project };

   // Get route hierarchy (from root to current page)
   const routeHierarchy = routeRegistry.getRouteHierarchy(routeName, context);

   // Transform route configurations into breadcrumb items
   const breadcrumbItems = routeHierarchy.map((route, index) => {
      // Get the label as string (it could be a function in the route configuration)
      const labelText =
         typeof route.label === "function"
            ? route.label(context)
            : (route.label as string) || "";

      // Generate a stable key
      const itemKey =
         typeof route.key === "function"
            ? `route-${index}` // Use index as fallback when key is a function
            : (route.key as string) || `route-${index}`;

      // For the Project route, use a project icon
      if (route.name === RouteNames.PROJECT) {
         return {
            title: (
               <Link
                  to={getProjectHomePath(project)}
                  title={`${project?.projectName}`}
               >
                  <ProjectOutlined />
               </Link>
            ),
            key: itemKey
         };
      }

      // For other routes
      return {
         title:
            index === routeHierarchy.length - 1 ? (
               // Current route: just show text, no link
               labelText
            ) : (
               // Parent route: add link
               <Link to={route.path as string} key={itemKey}>
                  {labelText}
               </Link>
            ),
         key: itemKey
      };
   });

   // Don't show breadcrumb if we're at the root route
   if (routeHierarchy.length <= 1) {
      return null;
   }

   return <Breadcrumb items={breadcrumbItems} separator={<span>›</span>} />;
};

export default BreadcrumbNav;
