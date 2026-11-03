import { useCallback, useMemo } from "react";
import { useLocation } from "react-router-dom";

interface RouteRegistryLike<TRouteName extends string, TRouteConfig, TContext> {
   findRouteByPath: (pathname: string) => TRouteConfig | null;
   getRouteConfig: (routeName: TRouteName, context?: TContext) => TRouteConfig;
   getRouteKey: (
      routeConfig: TRouteConfig,
      context?: TContext
   ) => string | undefined;
}

export const createRouteHook = <
   TRouteName extends string,
   TRouteConfig,
   TContext = never
>(
   routeRegistry: RouteRegistryLike<TRouteName, TRouteConfig, TContext>
) => {
   return function useRouteCore() {
      const location = useLocation();
      const currentPath = location.pathname;

      const queryParams = useMemo(
         () => new URLSearchParams(location.search),
         [location.search]
      );

      const getQueryParam = useCallback(
         (param: string) => queryParams.get(param),
         [queryParams]
      );

      const currentRoute = useMemo(
         () => routeRegistry.findRouteByPath(currentPath),
         [currentPath]
      );

      const getResolvedRouteConfig = useCallback(
         (routeName: TRouteName, context?: TContext) =>
            routeRegistry.getRouteConfig(routeName, context),
         []
      );

      const getResolvedRoutePath = useCallback(
         (routeName: TRouteName, context?: TContext) => {
            const routeConfig = routeRegistry.getRouteConfig(
               routeName,
               context
            );
            const { path } = routeConfig as { path: unknown };

            if (typeof path !== "string") {
               throw new Error(
                  `Resolved path for route "${routeName}" is not a string`
               );
            }

            return path;
         },
         []
      );

      const getResolvedRouteKey = useCallback(
         (routeConfig: TRouteConfig, context?: TContext) =>
            routeRegistry.getRouteKey(routeConfig, context),
         []
      );

      return {
         currentPath,
         queryParams,
         getQueryParam,
         currentRoute,
         getResolvedRouteConfig,
         getResolvedRoutePath,
         getResolvedRouteKey
      };
   };
};
