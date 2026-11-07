import type { LayoutRouteConfig, RouteConfig } from "@/types";
import { renderLayoutRoutes } from "@kontext-tech/app-runtime/router";
import ProjectRouteWrapper from "./ProjectRouteWrapper";

export const createRouteElements = (mainRoutes: LayoutRouteConfig[]) =>
   renderLayoutRoutes(mainRoutes, (route: RouteConfig, Element) => (
      <ProjectRouteWrapper route={route} Element={Element} />
   ));
