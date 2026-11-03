import { createPreloadableLazyWithProps } from "@kontext-tech/ui";

interface ProjectSelectorProps {
   inSidebar?: boolean;
   collapsed?: boolean;
}

const ProjectSelectorLazy =
   createPreloadableLazyWithProps<ProjectSelectorProps>(
      () => import("./ProjectSelector")
   );

export default ProjectSelectorLazy;
