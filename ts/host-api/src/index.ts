import type {
   AccessTokenResponse,
   CultureInfoModel,
   PaginatedListOfProjectModel,
   ProjectModel,
   SiteConfigResponse,
   UserWithRolesModel
} from "@kontext-labs/schema";

export type HostMode = "local" | "hosted";

export type HostUser = UserWithRolesModel;
export type HostProject = ProjectModel;
export type HostConfig = SiteConfigResponse;

export interface HostAuthBootstrap {
   mode: HostMode;
   authenticated: boolean;
   loginUrl?: string | null;
   logoutUrl?: string | null;
   accessToken?: AccessTokenResponse | null;
   user?: HostUser | null;
   projectRoles?: Record<string, string[]>;
   permissions?: string[];
   expiresAt?: string | null;
}

export interface HostAuthMe {
   mode: HostMode;
   authenticated: boolean;
   user: HostUser | null;
   projectRoles: Record<string, string[]>;
   permissions: string[];
   expiresAt?: string | null;
}

export interface HostClientOptions {
   basePath: string;
   accessToken?: string;
   credentials?: RequestCredentials;
   headers?: Record<string, string>;
}

export interface HostProjectListParams {
   filter?: string;
   pageIndex?: number;
   pageSize?: number;
   roleFilters?: string[];
   includePublic?: boolean;
   includePrivate?: boolean;
   includeDeleted?: boolean;
}

export class HostClient {
   private readonly basePath: string;
   private readonly accessToken?: string;
   private readonly credentials?: RequestCredentials;
   private readonly headers: Record<string, string>;

   constructor(options: HostClientOptions) {
      this.basePath = options.basePath.replace(/\/$/, "");
      this.accessToken = options.accessToken;
      this.credentials = options.credentials;
      this.headers = options.headers ?? {};
   }

   async bootstrap(): Promise<HostAuthBootstrap> {
      return this.request<HostAuthBootstrap>("/host/auth/bootstrap");
   }

   async me(): Promise<HostAuthMe> {
      return this.request<HostAuthMe>("/host/auth/me");
   }

   async refresh(): Promise<HostAuthBootstrap> {
      return this.request<HostAuthBootstrap>("/host/auth/refresh", {
         method: "POST"
      });
   }

   async logout(): Promise<void> {
      await this.request<void>("/host/auth/logout", { method: "POST" });
   }

   async getConfig(): Promise<HostConfig> {
      return this.request<HostConfig>("/host/config");
   }

   async getProjects(
      params: HostProjectListParams = {}
   ): Promise<PaginatedListOfProjectModel> {
      return this.request<PaginatedListOfProjectModel>(
         this.withQuery("/host/projects", params)
      );
   }

   async getProjectByCode(projectCode: string): Promise<HostProject> {
      return this.request<HostProject>(
         `/host/projects/code/${encodeURIComponent(projectCode)}`
      );
   }

   async getCulture(): Promise<CultureInfoModel[]> {
      return this.request<CultureInfoModel[]>("/host/culture");
   }

   private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
      const headers = new Headers(init.headers);
      for (const [key, value] of Object.entries(this.headers)) {
         headers.set(key, value);
      }
      if (this.accessToken && !headers.has("Authorization")) {
         headers.set("Authorization", `Bearer ${this.accessToken}`);
      }

      const response = await fetch(`${this.basePath}${path}`, {
         ...init,
         credentials: init.credentials ?? this.credentials,
         headers
      });

      if (!response.ok) {
         const error = new Error(
            `Host API request failed: ${response.status} ${response.statusText}`
         );
         (error as Error & { response: Response }).response = response;
         throw error;
      }

      if (response.status === 204) {
         return undefined as T;
      }

      return (await response.json()) as T;
   }

   private withQuery(path: string, params: object): string {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(
         params as Record<string, unknown | unknown[]>
      )) {
         if (value === undefined || value === null) continue;
         if (Array.isArray(value)) {
            value.forEach((item) => {
               if (item !== undefined && item !== null) {
                  searchParams.append(key, String(item));
               }
            });
         } else {
            searchParams.set(key, String(value));
         }
      }
      const query = searchParams.toString();
      return query ? `${path}?${query}` : path;
   }
}
