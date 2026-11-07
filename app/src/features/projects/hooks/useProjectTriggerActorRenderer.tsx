import { getTriggerActorLabel } from "@kontext-tech/job";
import { useProject } from "@kontext-tech/project";
import type { TriggerActorModel } from "@kontext-tech/schema";
import { useCallback, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useRoute } from "@/hooks/useRoute";

/**
 * Renders a job trigger actor as a link to the owning notebook/chat session/
 * file within the current project, falling back to its plain label. Shared by
 * the job runs page and any host that opens job run details (e.g. notebooks).
 */
export function useProjectTriggerActorRenderer(): (
   actor: TriggerActorModel
) => ReactNode {
   const { currentProject } = useProject();
   const {
      getNotebookDetailPath,
      getProjectChatSessionDetailPath,
      getFileDetailPath
   } = useRoute();

   return useCallback(
      (actor: TriggerActorModel) => {
         const label = getTriggerActorLabel(actor) ?? "Unknown";

         if (actor.id && currentProject) {
            if (actor.type === "Notebook") {
               return (
                  <Link to={getNotebookDetailPath(currentProject, actor.id)}>
                     {label}
                  </Link>
               );
            }
            if (actor.type === "ChatSession") {
               return (
                  <Link
                     to={getProjectChatSessionDetailPath(
                        currentProject,
                        actor.id
                     )}
                  >
                     {label}
                  </Link>
               );
            }
            if (actor.type === "File") {
               return (
                  <Link to={getFileDetailPath(currentProject, actor.id)}>
                     {label}
                  </Link>
               );
            }
         }

         return <span>{label}</span>;
      },
      [
         currentProject,
         getNotebookDetailPath,
         getProjectChatSessionDetailPath,
         getFileDetailPath
      ]
   );
}
