import { useProjectStore } from "./projectStore";

export function useProject() {
   const currentProject = useProjectStore((state) => state.currentProject);
   const isProjectLoading = useProjectStore((state) => state.isProjectLoading);
   const projectNotFound = useProjectStore((state) => state.projectNotFound);
   const error = useProjectStore((state) => state.error);
   const setCurrentProject = useProjectStore(
      (state) => state.setCurrentProject
   );

   return {
      currentProject,
      setCurrentProject,
      isProjectLoading,
      projectNotFound,
      error
   };
}
