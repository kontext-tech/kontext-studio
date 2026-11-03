import type {
   BaseLayoutRouteConfig,
   BaseRouteConfig,
   RouteContextValue
} from "@kontext-labs/common/utils";
import React from "react";

export type SharedRouteContextValue<TContext, TValue> = RouteContextValue<
   TContext,
   TValue
>;

export interface SharedRouteConfig<
   TRouteName extends string,
   TContext = never
> extends BaseRouteConfig<
   TRouteName,
   React.FC,
   () => React.JSX.Element,
   TContext
> {
   icon?: string | React.ReactNode;
   fullWidth?: boolean;
}

export type SharedLayoutRouteConfig<TRouteConfig extends { layout: React.FC }> =
   BaseLayoutRouteConfig<TRouteConfig>;
