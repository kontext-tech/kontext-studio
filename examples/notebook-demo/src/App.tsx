import { ThemeProvider, useTheme } from "@kontext-tech/theme";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntdApp, ConfigProvider, Layout } from "antd";
import React, { useState } from "react";
import DemoHeader from "./components/DemoHeader";
import NotebookDemo from "./examples/NotebookDemo";

const { Content } = Layout;

const queryClient = new QueryClient({
   defaultOptions: {
      queries: {
         refetchOnWindowFocus: false,
         retry: 1,
         staleTime: 5 * 60 * 1000
      }
   }
});

const AppContent: React.FC = () => {
   const { themeConfig } = useTheme();
   const [currentPage, setCurrentPage] = useState<string>("notebook");

   return (
      <ConfigProvider theme={themeConfig}>
         <AntdApp>
            <Layout style={{ minHeight: "100vh" }}>
               <DemoHeader
                  currentPage={currentPage}
                  onPageChange={setCurrentPage}
               />
               <Content>
                  {currentPage === "notebook" ? <NotebookDemo /> : null}
               </Content>
            </Layout>
         </AntdApp>
      </ConfigProvider>
   );
};

const App: React.FC = () => {
   return (
      <QueryClientProvider client={queryClient}>
         <ThemeProvider>
            <AppContent />
         </ThemeProvider>
      </QueryClientProvider>
   );
};

export default App;
