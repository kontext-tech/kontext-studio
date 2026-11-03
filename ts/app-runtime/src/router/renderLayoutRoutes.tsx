import { Fragment } from "react";
import { Route } from "react-router-dom";

export interface RenderableRouteConfig {
   path: unknown;
   pathPattern: string;
   layout: React.FC;
   element: () => React.JSX.Element;
}

export interface RenderableLayoutRouteConfig<
   TRouteConfig extends RenderableRouteConfig
> {
   layout: React.FC;
   routes: TRouteConfig[];
}

export const renderLayoutRoutes = <
   TRouteConfig extends RenderableRouteConfig,
   TLayoutRouteConfig extends RenderableLayoutRouteConfig<TRouteConfig>
>(
   mainRoutes: TLayoutRouteConfig[],
   renderElement: (
      route: TRouteConfig,
      Element: React.ComponentType
   ) => React.ReactNode
) => (
   <Fragment>
      {mainRoutes.map((layoutConfig) => (
         <Route
            key={`layout-${layoutConfig.layout.name}`}
            element={<layoutConfig.layout />}
         >
            {layoutConfig.routes.map((route) => {
               const Element = route.element;

               return Element ? (
                  <Route
                     key={`route-${route.pathPattern ?? route.path}`}
                     path={route.pathPattern ?? route.path}
                     element={renderElement(route, Element)}
                  />
               ) : null;
            })}
         </Route>
      ))}
   </Fragment>
);
