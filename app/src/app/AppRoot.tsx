import { LoadingOutlined } from "@kontext-labs/icons";
import { ServiceProvider } from "@kontext-labs/app-runtime/context";
import { useTheme } from "@kontext-labs/theme";
import { useSiteConfigStore } from "@kontext-labs/site";
import { App as AntdApp, ConfigProvider } from "antd";
import { type ReactNode, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";

/**
 * Mounts the app's concrete API error handler. Must render *inside*
 * `<AntdApp>`: the handler resolves antd's message/modal context, and the
 * provider element this wraps sits above every route that consumes services.
 */
const ApiErrorHandlerMount = ({ children }: { children: ReactNode }) => {
   const apiErrorHandler = useApiErrorHandler();
   return (
      <ServiceProvider errorHandler={apiErrorHandler}>
         {children}
      </ServiceProvider>
   );
};

const AppRoot = () => {
   const { themeConfig } = useTheme();

   useEffect(() => {
      void useSiteConfigStore.getState().fetchSiteConfig();
   }, []);

   return (
      <ConfigProvider
         theme={{
            ...themeConfig,
            hashed: false
         }}
         spin={{
            indicator: <LoadingOutlined spin />
         }}
      >
         <AntdApp>
            <ApiErrorHandlerMount>
               <Outlet />
            </ApiErrorHandlerMount>
         </AntdApp>
      </ConfigProvider>
   );
};

export default AppRoot;
