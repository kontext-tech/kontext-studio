import type { ApiErrorResult } from "@kontext-tech/common/types";
import { createContext, useContext, type ReactNode } from "react";

/**
 * Default error handler for services created by this package's hooks.
 *
 * Service base classes call the handler for errors that belong to the
 * *global* UI (auth/session recovery, non-inline API failures); call paths
 * that render failures inline opt out at the service level. The app mounts
 * exactly one provider high in its shell with the concrete handler; hooks
 * fall back to it when no explicit handler is passed.
 */
export type ServiceErrorHandler = (error: ApiErrorResult) => Promise<void>;

export interface ServiceProviderProps {
   children: ReactNode;
   errorHandler?: ServiceErrorHandler;
}

const ServiceErrorHandlerContext = createContext<ServiceErrorHandler | null>(
   null
);

export function ServiceProvider({
   children,
   errorHandler
}: ServiceProviderProps) {
   return (
      <ServiceErrorHandlerContext.Provider value={errorHandler ?? null}>
         {children}
      </ServiceErrorHandlerContext.Provider>
   );
}

/**
 * The error handler provided by the nearest `ServiceProvider`, if mounted.
 * Returns `undefined` (not null) so callers can pass it straight through to
 * optional handler parameters.
 */
export function useOptionalDefaultServiceErrorHandler():
   ServiceErrorHandler | undefined {
   return useContext(ServiceErrorHandlerContext) ?? undefined;
}
