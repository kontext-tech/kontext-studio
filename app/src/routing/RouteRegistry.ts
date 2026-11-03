import type {
   ResolvedRouteAccessPolicy,
   RouteAccessPolicy,
   RouteConfig,
   RouteDefinition,
   RouteLayoutMetadata,
   RouteNames,
   RouteNavigationMetadata,
   RoutingContextInfo
} from "@/types";
import { BaseRouteRegistry } from "@kontext-labs/common/utils";
import { matchPath } from "react-router-dom";

export class RouteRegistry extends BaseRouteRegistry<
   RouteNames,
   RouteConfig,
   RoutingContextInfo
> {
   constructor(routeConfigs: Record<RouteNames, RouteConfig>) {
      super(
         routeConfigs,
         (pathPattern, pathname) => matchPath(pathPattern, pathname) !== null
      );
   }

   getRouteDefinition(
      routeName: RouteNames,
      context?: RoutingContextInfo
   ): RouteDefinition {
      const routeConfig = this.getRouteConfig(routeName, context);

      return {
         path: routeConfig.path,
         pathPattern: routeConfig.pathPattern,
         name: routeConfig.name,
         layout: routeConfig.layout,
         element: routeConfig.element,
         requiresProject: routeConfig.requiresProject
      };
   }

   getNavigationMetadata(
      routeName: RouteNames,
      context?: RoutingContextInfo
   ): RouteNavigationMetadata {
      const routeConfig = this.getRouteConfig(routeName, context);

      return {
         key: routeConfig.key,
         parentKey: routeConfig.parentKey,
         label: routeConfig.label,
         icon: routeConfig.icon,
         visible: routeConfig.visible
      };
   }

   getAccessPolicy(
      routeName: RouteNames,
      context?: RoutingContextInfo
   ): ResolvedRouteAccessPolicy {
      const routeConfig = this.getRawRouteConfig(routeName);
      const policy: RouteAccessPolicy = {
         isPublic: routeConfig.isPublic,
         allowedProjectRoles: routeConfig.allowedProjectRoles,
         allowedSystemRoles: routeConfig.allowedSystemRoles,
         allowedPermissionClaims: routeConfig.allowedPermissionClaims,
         requiredFeatures: routeConfig.requiredFeatures
      };

      return {
         ...policy,
         isPublic:
            typeof policy.isPublic === "function"
               ? policy.isPublic(context || {})
               : policy.isPublic
      };
   }

   getLayoutMetadata(routeName: RouteNames): RouteLayoutMetadata {
      const routeConfig = this.getRawRouteConfig(routeName);

      return {
         fullWidth: routeConfig.fullWidth,
         fullHeight: routeConfig.fullHeight,
         hideBreadcrumb: routeConfig.hideBreadcrumb
      };
   }
}
