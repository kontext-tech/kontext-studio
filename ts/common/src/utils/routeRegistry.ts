export type RouteContextValue<TContext, TValue> =
   TValue | ((context: TContext) => TValue);

export interface BaseRouteConfig<
   TRouteName extends string,
   TLayout = unknown,
   TElement = unknown,
   TContext = never
> {
   path: RouteContextValue<TContext, string>;
   pathPattern: string;
   name: TRouteName;
   layout: TLayout;
   element: TElement;
   key?: RouteContextValue<TContext, string>;
   parentKey?: RouteContextValue<TContext, string>;
   label?: RouteContextValue<TContext, string>;
}

export interface BaseLayoutRouteConfig<
   TRouteConfig extends { layout: unknown }
> {
   layout: TRouteConfig["layout"];
   routes: TRouteConfig[];
}

type MatchPathFn = (pathPattern: string, pathname: string) => boolean;

export class BaseRouteRegistry<
   TRouteName extends string,
   TRouteConfig extends BaseRouteConfig<TRouteName, unknown, unknown, TContext>,
   TContext = never
> {
   constructor(
      protected readonly routeConfigs: Record<TRouteName, TRouteConfig>,
      private readonly matchPath: MatchPathFn
   ) {}

   protected resolveContextValue<TValue>(
      value: RouteContextValue<TContext, TValue> | undefined,
      context?: TContext,
      errorMessage?: string
   ): TValue | undefined {
      if (typeof value !== "function") {
         return value;
      }

      if (!context) {
         throw new Error(errorMessage || "Context is required for this route");
      }

      return (value as (context: TContext) => TValue)(context);
   }

   getRawRouteConfig(routeName: TRouteName): TRouteConfig {
      const routeConfig = this.routeConfigs[routeName];

      if (!routeConfig) {
         throw new Error(
            `Route configuration not found for route ${routeName}`
         );
      }

      return routeConfig;
   }

   getRouteConfig(routeName: TRouteName, context?: TContext): TRouteConfig {
      const routeConfig = this.getRawRouteConfig(routeName);

      return {
         ...routeConfig,
         path: this.resolveContextValue(
            routeConfig.path,
            context,
            `Context is required for route path ${routeName}`
         ) as TRouteConfig["path"],
         key: this.resolveContextValue(
            routeConfig.key,
            context,
            `Context is required for route key ${routeName}`
         ) as TRouteConfig["key"],
         parentKey: this.resolveContextValue(
            routeConfig.parentKey,
            context,
            `Context is required for route parent key ${routeName}`
         ) as TRouteConfig["parentKey"],
         label: this.resolveContextValue(
            routeConfig.label,
            context,
            `Context is required for route label ${routeName}`
         ) as TRouteConfig["label"]
      };
   }

   getRouteKey(
      routeConfig: TRouteConfig,
      context?: TContext
   ): string | undefined {
      return this.resolveContextValue(
         routeConfig.key,
         context,
         `Context is required for route key of route ${routeConfig.pathPattern}`
      );
   }

   private getRouteParentKey(
      routeName: TRouteName,
      context?: TContext
   ): string | undefined {
      return this.resolveContextValue(
         this.getRawRouteConfig(routeName).parentKey,
         context,
         `Context is required for route parent key ${routeName}`
      );
   }

   getRouteHierarchy(
      routeName: TRouteName,
      context?: TContext
   ): TRouteConfig[] {
      const hierarchy: TRouteConfig[] = [];
      const parentKeyHierarchy: string[] = [];
      let currentRoute = routeName;
      let parentKey = this.getRouteParentKey(currentRoute, context);

      while (parentKey) {
         parentKeyHierarchy.push(parentKey);

         let parentRouteName: TRouteName | undefined;
         for (const name of Object.keys(this.routeConfigs) as TRouteName[]) {
            const config = this.routeConfigs[name];
            const routeKey = this.resolveContextValue(config.key, context);

            if (routeKey === parentKey) {
               parentRouteName = name;
               break;
            }
         }

         if (!parentRouteName) {
            break;
         }

         currentRoute = parentRouteName;
         parentKey = this.getRouteParentKey(currentRoute, context);
      }

      for (const resolvedParentKey of [...parentKeyHierarchy].reverse()) {
         for (const name of Object.keys(this.routeConfigs) as TRouteName[]) {
            const config = this.routeConfigs[name];
            const routeKey = this.resolveContextValue(config.key, context);

            if (routeKey === resolvedParentKey) {
               hierarchy.push(this.getRouteConfig(name, context));
               break;
            }
         }
      }

      hierarchy.push(this.getRouteConfig(routeName, context));

      return hierarchy;
   }

   getLayoutRouteConfig(
      context?: TContext,
      shouldIncludeRoute?: (routeName: TRouteName) => boolean
   ): BaseLayoutRouteConfig<TRouteConfig>[] {
      const layoutMap = new Map<TRouteConfig["layout"], TRouteConfig[]>();

      for (const routeName of Object.keys(this.routeConfigs) as TRouteName[]) {
         const routeConfig = this.routeConfigs[routeName];
         if (shouldIncludeRoute && !shouldIncludeRoute(routeName)) {
            continue;
         }

         const layout = routeConfig.layout;
         if (!layoutMap.has(layout)) {
            layoutMap.set(layout, []);
         }

         const configToPush = context
            ? this.getRouteConfig(routeName, context)
            : this.getRawRouteConfig(routeName);

         layoutMap.get(layout)?.push(configToPush);
      }

      return Array.from(layoutMap.entries()).map(([layout, routes]) => ({
         layout,
         routes
      }));
   }

   findRouteByPath(pathname: string): TRouteConfig | null {
      for (const routeName of Object.keys(this.routeConfigs) as TRouteName[]) {
         const route = this.routeConfigs[routeName];
         if (
            (typeof route.path === "string" && route.path === pathname) ||
            this.matchPath(route.pathPattern, pathname)
         ) {
            return route;
         }
      }

      return null;
   }
}
