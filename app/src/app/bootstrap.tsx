import { ThemeProvider } from "@kontext-labs/theme";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { PermissionProvider } from "@/context/AppPermissionContext";
import { appQueryClient } from "@/query/queryClient";
import { appRouter } from "@/routing/appRouter";
import { scheduleLikelyRoutePreloads } from "@/routing/scheduleLikelyRoutePreloads";
import "@/styles/index.scss";

scheduleLikelyRoutePreloads();

createRoot(document.getElementById("root")!).render(
   <StrictMode>
      <QueryClientProvider client={appQueryClient}>
         <ThemeProvider>
            <PermissionProvider>
               <RouterProvider router={appRouter} />
            </PermissionProvider>
         </ThemeProvider>
      </QueryClientProvider>
   </StrictMode>
);
