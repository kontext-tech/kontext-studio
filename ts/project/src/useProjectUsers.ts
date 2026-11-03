import { ProjectRole } from "@kontext-labs/auth";
import { useService } from "@kontext-labs/app-runtime/hooks";
import { useUiApp } from "@kontext-labs/ui";
import { ApiResult } from "@kontext-labs/common";
import type { ApiErrorResult } from "@kontext-labs/common/types";
import type {
   PaginatedListOfUserWithProjectRolesModel,
   UserWithProjectRolesModel
} from "@kontext-labs/schema";
import { useCallback, useEffect, useRef, useState } from "react";
import { ProjectService } from "./ProjectService";

export interface UseProjectUsersReturn {
   users: UserWithProjectRolesModel[];
   isLoading: boolean;
   error: string | null;
   pageIndex: number;
   pageSize: number;
   totalCount: number;
   isSubmitting: boolean;
   setPageIndex: (pageIndex: number) => void;
   setPageSize: (pageSize: number) => void;
   filter: string;
   handleSearch: (value: string) => void;
   handleAddUser: (values: {
      userId: string;
      roles: string[];
   }) => Promise<boolean>;
   handleEditUserRoles: (
      userId: string,
      values: { roles: string[] }
   ) => Promise<boolean>;
   handleRemoveUser: (userId: string) => Promise<boolean>;
}

export const useProjectUsers = (
   projectId: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
): UseProjectUsersReturn => {
   const [users, setUsers] = useState<UserWithProjectRolesModel[]>([]);
   const [isLoading, setIsLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [pageIndex, setPageIndex] = useState(1);
   const [pageSize, setPageSize] = useState(10);
   const [totalCount, setTotalCount] = useState(0);
   const [filter, setFilter] = useState("");
   const [isSubmitting, setIsSubmitting] = useState(false);
   const { message } = useUiApp();

   const projectService = useRef(
      useService(ProjectService, errorHandler)
   ).current;

   const loadUsers = useCallback(async (): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const result: ApiResult<PaginatedListOfUserWithProjectRolesModel> =
         await projectService.getProjectUsers(
            projectId,
            filter,
            pageIndex,
            pageSize
         );

      if (result.succeed && result.data) {
         setUsers(result.data.items || []);
         setTotalCount(result.data.totalCount || 0);
      } else if (result.error) {
         const errorMessage =
            result.error.messages && result.error.messages.length > 0
               ? result.error.messages[0]
               : "Unknown error";
         setError(`Failed to load project users: ${errorMessage}`);
      }

      setIsLoading(false);
   }, [filter, pageIndex, pageSize, projectId, projectService]);

   useEffect(() => {
      void loadUsers();
   }, [loadUsers]);

   const handleSearch = (value: string): void => {
      setFilter(value);
      setPageIndex(1);
   };

   const handleAddUser = async (values: {
      userId: string;
      roles: string[];
   }): Promise<boolean> => {
      setIsSubmitting(true);
      setError(null);

      const projectRoles: ProjectRole[] = values.roles as ProjectRole[];
      const result = await projectService.updateUserProjectRoles(
         projectId,
         values.userId,
         projectRoles
      );

      if (result.succeed) {
         message.success("User added successfully!");
         void loadUsers();
         setIsSubmitting(false);
         return true;
      }

      setError(result.error?.messages?.join(", ") || "Failed to add user");
      setIsSubmitting(false);
      return false;
   };

   const handleEditUserRoles = async (
      userId: string,
      values: { roles: string[] }
   ): Promise<boolean> => {
      setIsSubmitting(true);
      setError(null);

      const projectRoles: ProjectRole[] = values.roles as ProjectRole[];
      const result = await projectService.updateUserProjectRoles(
         projectId,
         userId,
         projectRoles
      );

      if (result.succeed) {
         message.success("User roles updated successfully!");
         void loadUsers();
         setIsSubmitting(false);
         return true;
      }

      const errorMessage =
         result.error?.messages?.join(", ") || "Failed to update user";
      setError(errorMessage);
      message.error(errorMessage);
      setIsSubmitting(false);
      return false;
   };

   const handleRemoveUser = async (userId: string): Promise<boolean> => {
      setError(null);

      const result = await projectService.updateUserProjectRoles(
         projectId,
         userId,
         []
      );

      if (result.succeed) {
         message.success("User removed from project successfully!");
         void loadUsers();
         return true;
      }

      setError(result.error?.messages?.join(", ") || "Failed to remove user");
      setIsSubmitting(false);
      return false;
   };

   return {
      users,
      isLoading,
      error,
      pageIndex,
      pageSize,
      totalCount,
      isSubmitting,
      setPageIndex,
      setPageSize,
      filter,
      handleSearch,
      handleAddUser,
      handleEditUserRoles,
      handleRemoveUser
   };
};
