import { create } from "zustand";
import { persist } from "zustand/middleware";
import { PROJECT_WORKSPACE_MODES } from "../constants";

export type ProjectWorkspaceMode =
   (typeof PROJECT_WORKSPACE_MODES)[keyof typeof PROJECT_WORKSPACE_MODES];

interface LayoutState {
   sideMenuCollapsed: boolean;
   projectWorkspaceMode: ProjectWorkspaceMode;
   setSideMenuCollapsed: (collapsed: boolean) => void;
   setProjectWorkspaceMode: (mode: ProjectWorkspaceMode) => void;
   toggleSideMenu: () => void;
}

export const useLayoutStore = create<LayoutState>()(
   persist(
      (set, get) => ({
         sideMenuCollapsed: false,
         projectWorkspaceMode: PROJECT_WORKSPACE_MODES.CHAT_FIRST,
         setSideMenuCollapsed: (collapsed: boolean) => {
            set({ sideMenuCollapsed: collapsed });
         },
         setProjectWorkspaceMode: (mode: ProjectWorkspaceMode) => {
            set({ projectWorkspaceMode: mode });
         },
         toggleSideMenu: () => {
            set({ sideMenuCollapsed: !get().sideMenuCollapsed });
         }
      }),
      {
         name: "kontext-layout-storage"
      }
   )
);
