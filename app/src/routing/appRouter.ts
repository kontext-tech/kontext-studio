import { createElement } from "react";
import {
   Route,
   createBrowserRouter,
   createRoutesFromElements
} from "react-router-dom";
import MainApp from "../App";
import { createRouteElements } from "./RenderRoutes";
import { getLayoutRouteConfig } from "./routes";

export const appRouter = createBrowserRouter(
   createRoutesFromElements(
      createElement(
         Route,
         { element: createElement(MainApp) },
         createRouteElements(getLayoutRouteConfig())
      )
   ),
   {
      basename: "/"
   }
);
