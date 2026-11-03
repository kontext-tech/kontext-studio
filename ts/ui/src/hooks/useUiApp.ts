import { App } from "antd";

export const useUiApp = () => {
   const app = App.useApp();

   if (app === undefined) {
      throw new Error("useUiApp must be used within an App provider");
   }

   return app;
};
