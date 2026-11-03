import type { ApiAuthContext, ApiErrorResult } from "../types/api";

export interface ServiceContainerOptions {
   authContext?: ApiAuthContext;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

export interface ConfigurableService {
   updateAuthContext?: (authContext: ApiAuthContext) => void;
   setErrorHandler?: (
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => void;
}

export type ServiceFactory<T> = (container: ServiceContainer) => T;

export class ServiceContainer {
   private authContext: ApiAuthContext;
   private errorHandler?: (error: ApiErrorResult) => Promise<void>;
   private readonly serviceInstances = new Map<string, unknown>();

   constructor(options: ServiceContainerOptions = {}) {
      this.authContext = { ...(options.authContext ?? {}) };
      this.errorHandler = options.errorHandler;
   }

   public setAuthContext(context: ApiAuthContext = {}): void {
      this.authContext = { ...context };
      this.syncInstances();
   }

   public mergeAuthContext(context: Partial<ApiAuthContext>): void {
      this.authContext = {
         ...this.authContext,
         ...context
      };
      this.syncInstances();
   }

   public createAuthContext(
      overrides: Partial<ApiAuthContext> = {}
   ): ApiAuthContext {
      return {
         ...this.authContext,
         ...overrides
      };
   }

   public setErrorHandler(
      handler?: (error: ApiErrorResult) => Promise<void>
   ): void {
      this.errorHandler = handler;
      this.syncInstances();
   }

   public getAuthContext(): ApiAuthContext {
      return this.createAuthContext();
   }

   public getErrorHandler():
      ((error: ApiErrorResult) => Promise<void>) | undefined {
      return this.errorHandler;
   }

   public has(key: string): boolean {
      return this.serviceInstances.has(key);
   }

   public register<T>(key: string, instance: T): T {
      const configuredInstance = this.configureService(instance);
      this.serviceInstances.set(key, configuredInstance);
      return configuredInstance;
   }

   public getOrCreate<T>(key: string, factory: ServiceFactory<T>): T {
      if (!this.serviceInstances.has(key)) {
         return this.register(key, factory(this));
      }

      return this.resolve<T>(key);
   }

   public resolve<T>(key: string): T {
      const instance = this.serviceInstances.get(key);

      if (!instance) {
         throw new Error(`Service not found: ${key}`);
      }

      return instance as T;
   }

   public remove(key: string): void {
      this.serviceInstances.delete(key);
   }

   public clear(): void {
      this.serviceInstances.clear();
   }

   private syncInstances(): void {
      this.serviceInstances.forEach((instance) => {
         this.configureService(instance);
      });
   }

   private configureService<T>(instance: T): T {
      const configurableService = instance as ConfigurableService;

      configurableService.updateAuthContext?.(this.createAuthContext());
      configurableService.setErrorHandler?.(this.errorHandler);

      return instance;
   }
}
