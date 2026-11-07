import type { ProjectModel } from "@kontext-tech/schema";
import {
   LOCAL_STORAGE_KEYS,
   ServiceContainer,
   logger,
   type ApiErrorResult
} from "@kontext-tech/common";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { ProjectService } from "./ProjectService";

const projectServiceContainer = new ServiceContainer();

function getProjectService(
   accessToken?: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
) {
   projectServiceContainer.setAuthContext({ accessToken });
   projectServiceContainer.setErrorHandler(errorHandler);

   return projectServiceContainer.getOrCreate(
      "project-service",
      (container: ServiceContainer) => {
         return new ProjectService(
            container.createAuthContext(),
            container.getErrorHandler()
         );
      }
   );
}

interface ProjectStore {
   // State
   currentProject: ProjectModel | null;
   isProjectLoading: boolean;
   projectNotFound: boolean;
   error: string | null;

   // Internal state for request deduplication
   _pendingProjectCode: string | null;
   _syncInProgress: boolean;

   // Actions
   setCurrentProject: (project: ProjectModel | null) => void;
   setProjectLoading: (loading: boolean) => void;
   setProjectNotFound: (notFound: boolean) => void;
   setError: (error: string | null) => void;
   updateCurrentProject: (
      projectCode: string,
      accessToken?: string,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      forceRefresh?: boolean
   ) => Promise<void>;
   clearProject: () => void;
   syncWithUrl: (
      projectCode: string | undefined,
      accessToken?: string,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<void>;
}

const useProjectStore = create<ProjectStore>()(
   persist(
      (set, get) => ({
         // Initial state
         currentProject: null,
         isProjectLoading: false,
         projectNotFound: false,
         error: null,
         _pendingProjectCode: null,
         _syncInProgress: false,

         // Actions
         setCurrentProject: (project) => {
            set({ currentProject: project });
         },

         setProjectLoading: (loading) => {
            set({ isProjectLoading: loading });
         },

         setProjectNotFound: (notFound) => {
            set({ projectNotFound: notFound });
         },

         setError: (error) => {
            set({ error });
         },

         updateCurrentProject: async (
            projectCode: string,
            accessToken?: string,
            errorHandler?: (error: ApiErrorResult) => Promise<void>,
            forceRefresh = false
         ) => {
            const { currentProject, _pendingProjectCode } = get();

            // Reset projectNotFound state
            set({ projectNotFound: false });

            // Don't set loading state if we're already showing the correct project
            if (
               !forceRefresh &&
               projectCode === currentProject?.projectCode &&
               currentProject !== null
            ) {
               return;
            }

            // Prevent duplicate requests for the same project
            if (_pendingProjectCode === projectCode) {
               logger.debug(
                  `[ProjectStore] Request for "${projectCode}" already in progress, skipping duplicate`
               );
               return;
            }

            // Mark this project as pending to prevent duplicate requests
            set({
               isProjectLoading: true,
               error: null,
               _pendingProjectCode: projectCode
            });

            try {
               logger.debug(
                  `[ProjectStore] Fetching project: "${projectCode}"`
               );

               // Always fetch project details from the API
               const response = await getProjectService(
                  accessToken,
                  errorHandler
               ).getProjectByCode(projectCode);

               if (response.succeed && response.data) {
                  set({
                     currentProject: response.data,
                     projectNotFound: false,
                     isProjectLoading: false,
                     _pendingProjectCode: null
                  });
                  logger.debug(
                     `[ProjectStore] Successfully loaded project: "${projectCode}"`
                  );
               } else {
                  set({
                     currentProject: null,
                     projectNotFound: true,
                     error: response.error?.title || "Failed to fetch project",
                     isProjectLoading: false,
                     _pendingProjectCode: null
                  });
                  logger.debug(
                     `[ProjectStore] Failed to load project: "${projectCode}"`
                  );
               }
            } catch (err) {
               console.error(
                  `[ProjectStore] Error fetching project "${projectCode}":`,
                  err
               );
               set({
                  currentProject: null,
                  projectNotFound: true,
                  error: "Failed to fetch project",
                  isProjectLoading: false,
                  _pendingProjectCode: null
               });
            }
         },

         clearProject: () => {
            logger.debug(`[ProjectStore] Clearing project`);
            set({
               currentProject: null,
               isProjectLoading: false,
               projectNotFound: false,
               error: null,
               _pendingProjectCode: null,
               _syncInProgress: false
            });
         },

         syncWithUrl: async (
            projectCode: string | undefined,
            accessToken?: string,
            errorHandler?: (error: ApiErrorResult) => Promise<void>
         ) => {
            const { currentProject, _syncInProgress } = get();
            const currentProjectCode = currentProject?.projectCode;

            // Prevent multiple concurrent sync operations
            if (_syncInProgress) {
               logger.debug(
                  `[ProjectStore] syncWithUrl already in progress, skipping call for "${projectCode}"`
               );
               return;
            }

            logger.debug(
               `[ProjectStore] syncWithUrl: projectCode="${projectCode}", currentProject="${currentProjectCode}"`
            );

            if (projectCode) {
               // URL has a project code
               if (
                  currentProjectCode?.toLowerCase() ===
                  projectCode.toLowerCase()
               ) {
                  // Force refresh from API to avoid stale project configuration
                  // after browser refresh/session hydration.
                  set({ _syncInProgress: true });
                  try {
                     await get().updateCurrentProject(
                        projectCode,
                        accessToken,
                        errorHandler,
                        true
                     );
                  } finally {
                     set({ _syncInProgress: false });
                  }

                  logger.debug(
                     `[ProjectStore] Project refreshed: "${projectCode}"`
                  );
                  return;
               }

               // Need to load the project from the URL
               logger.debug(`[ProjectStore] Loading project: "${projectCode}"`);
               set({ _syncInProgress: true });
               try {
                  await get().updateCurrentProject(
                     projectCode,
                     accessToken,
                     errorHandler
                  );
               } finally {
                  set({ _syncInProgress: false });
               }
            } else {
               // No project code in URL
               if (currentProjectCode) {
                  // Clear current project if we have one but URL doesn't specify a project
                  logger.debug(
                     `[ProjectStore] Clearing project because no projectCode in URL`
                  );
                  set({ _syncInProgress: true });
                  try {
                     get().clearProject();
                  } finally {
                     set({ _syncInProgress: false });
                  }
               }
            }
         }
      }),
      {
         // The URL is the authority for the selected project; the persisted
         // copy is only a cache to warm the first paint before syncWithUrl
         // resolves (see syncWithUrl: it refreshes on match, loads on change,
         // and clears when the URL has no project code).
         name: LOCAL_STORAGE_KEYS.CURRENT_PROJECT,
         storage: createJSONStorage(() => sessionStorage),
         // Only persist the current project data, not loading/error states or internal state
         partialize: (state) => ({
            currentProject: state.currentProject
         }),
         // Skip persistence if there's no current project
         skipHydration: false,
         onRehydrateStorage: () => (state) => {
            // Always reset loading and error states on hydration
            if (state) {
               state.isProjectLoading = false;
               state.projectNotFound = false;
               state.error = null;
            }
         }
      }
   )
);

export { useProjectStore };
