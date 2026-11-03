import type { ApiErrorResult } from "@kontext-tech/common";
import { useUserStore } from "@kontext-tech/identity";
import { CatalogService } from "@kontext-tech/project";
import type {
   CatalogConnection,
   CatalogEntitySummary,
   CatalogNamespaceSummary,
   ProjectModel
} from "@kontext-tech/schema";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type ScopeOverrides = {
   connectionId?: string;
   namespaceName?: string;
   entityId?: string;
};

export interface UseCatalogScopeReturn {
   connections: CatalogConnection[];
   namespaces: CatalogNamespaceSummary[];
   entities: CatalogEntitySummary[];
   selectedConnectionId?: string;
   selectedNamespace?: string;
   selectedEntityId?: string;
   selectedConnection: CatalogConnection | null;
   selectedEntity: CatalogEntitySummary | null;
   isCatalogLoading: boolean;
   isEntitiesLoading: boolean;
   hasLoadedEntities: boolean;
   catalogError: string | null;
   hasScopeChoices: boolean;
   refreshCatalogScope: (overrides?: ScopeOverrides) => Promise<void>;
   loadEntities: (namespaceName?: string) => Promise<void>;
   clearEntitySelection: () => void;
   selectConnection: (connectionId: string) => Promise<void>;
   selectNamespace: (namespaceName?: string) => Promise<void>;
   selectEntity: (entityId?: string) => void;
}

const getDefaultConnection = (
   connections: CatalogConnection[],
   preferredConnectionId?: string
) =>
   connections.find(
      (connection) =>
         connection.id === preferredConnectionId && connection.isQueryReady
   ) ||
   connections.find(
      (connection) =>
         connection.providerKind === "iceberg_internal" &&
         connection.isQueryReady
   ) ||
   connections.find(
      (connection) =>
         connection.providerKind === "iceberg_internal" &&
         connection.connectionKind === "internal"
   ) ||
   connections.find((connection) => connection.isQueryReady);

const getDefaultNamespace = (
   namespaces: CatalogNamespaceSummary[],
   preferredNamespace?: string
) => {
   return namespaces.find((namespace) => namespace.name === preferredNamespace)
      ?.name;
};

export function useCatalogScope(
   project: ProjectModel,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
): UseCatalogScopeReturn {
   const tokens = useUserStore((state) => state.tokens);
   const catalogService = useDataService(CatalogService, errorHandler);

   const [connections, setConnections] = useState<CatalogConnection[]>([]);
   const [namespaces, setNamespaces] = useState<CatalogNamespaceSummary[]>([]);
   const [entities, setEntities] = useState<CatalogEntitySummary[]>([]);
   const [selectedConnectionId, setSelectedConnectionId] = useState<
      string | undefined
   >(undefined);
   const [selectedNamespace, setSelectedNamespace] = useState<
      string | undefined
   >(undefined);
   const [selectedEntityId, setSelectedEntityId] = useState<string | undefined>(
      undefined
   );
   const [isCatalogLoading, setIsCatalogLoading] = useState(false);
   const [isEntitiesLoading, setIsEntitiesLoading] = useState(false);
   const [catalogError, setCatalogError] = useState<string | null>(null);
   const [hasLoadedEntities, setHasLoadedEntities] = useState(false);

   const bootstrapRequestRef = useRef(0);
   const entityRequestRef = useRef(0);
   const selectedConnectionRef = useRef<string | undefined>(undefined);
   const selectedNamespaceRef = useRef<string | undefined>(undefined);
   const selectedEntityRef = useRef<string | undefined>(undefined);
   const refreshCatalogScopeRef = useRef<
      UseCatalogScopeReturn["refreshCatalogScope"] | undefined
   >(undefined);

   useEffect(() => {
      selectedConnectionRef.current = selectedConnectionId;
   }, [selectedConnectionId]);

   useEffect(() => {
      selectedNamespaceRef.current = selectedNamespace;
   }, [selectedNamespace]);

   useEffect(() => {
      selectedEntityRef.current = selectedEntityId;
   }, [selectedEntityId]);

   const loadEntities = useCallback(
      async (namespaceName?: string) => {
         if (!project.id || !tokens?.accessToken) {
            return;
         }

         const connectionId = selectedConnectionRef.current;
         const namespaceToLoad =
            namespaceName ?? selectedNamespaceRef.current ?? undefined;

         if (!connectionId || !namespaceToLoad) {
            setEntities([]);
            setSelectedEntityId(undefined);
            setHasLoadedEntities(false);
            return;
         }

         const connection = connections.find(
            (item) => item.id === connectionId
         );
         if (!connection?.isQueryReady) {
            setEntities([]);
            setSelectedEntityId(undefined);
            setHasLoadedEntities(false);
            setCatalogError(
               "Select a ready data source before loading tables."
            );
            return;
         }

         const requestId = entityRequestRef.current + 1;
         entityRequestRef.current = requestId;
         setIsEntitiesLoading(true);

         try {
            const entitiesResult = await catalogService.listEntities(
               project.id,
               connectionId,
               namespaceToLoad
            );

            if (entityRequestRef.current !== requestId) {
               return;
            }

            const nextEntities =
               entitiesResult.succeed && entitiesResult.data
                  ? entitiesResult.data
                  : [];
            setEntities(nextEntities);
            setHasLoadedEntities(true);
            setCatalogError(
               entitiesResult.succeed
                  ? null
                  : entitiesResult.error?.title ||
                       "Failed to load data source tables."
            );

            const preferredEntityId = selectedEntityRef.current;
            const nextEntityId = preferredEntityId
               ? nextEntities.find((entity) => entity.id === preferredEntityId)
                    ?.id
               : undefined;
            setSelectedEntityId(nextEntityId);
         } finally {
            if (entityRequestRef.current === requestId) {
               setIsEntitiesLoading(false);
            }
         }
      },
      [catalogService, connections, project.id, tokens?.accessToken]
   );

   const refreshCatalogScope = useCallback(
      async (overrides: ScopeOverrides = {}) => {
         if (!project.id || !tokens?.accessToken) {
            return;
         }

         const requestId = bootstrapRequestRef.current + 1;
         bootstrapRequestRef.current = requestId;
         setIsCatalogLoading(true);

         try {
            const connectionsResult = await catalogService.listConnections(
               project.id
            );

            if (bootstrapRequestRef.current !== requestId) {
               return;
            }

            if (!connectionsResult.succeed || !connectionsResult.data) {
               setConnections([]);
               setNamespaces([]);
               setEntities([]);
               setSelectedConnectionId(undefined);
               setSelectedNamespace(undefined);
               setSelectedEntityId(undefined);
               setHasLoadedEntities(false);
               setCatalogError(
                  connectionsResult.error?.title ||
                     "Failed to load project data sources."
               );
               return;
            }

            const nextConnections = connectionsResult.data.filter(
               (connection) => connection.enabled !== false
            );
            setConnections(nextConnections);
            setCatalogError(null);

            const nextConnection = getDefaultConnection(
               nextConnections,
               overrides.connectionId ?? selectedConnectionRef.current
            );
            const nextConnectionId = nextConnection?.id;
            setSelectedConnectionId(nextConnectionId);

            if (!nextConnectionId) {
               setNamespaces([]);
               setEntities([]);
               setSelectedNamespace(undefined);
               setSelectedEntityId(undefined);
               setHasLoadedEntities(false);
               if (nextConnections.length > 0) {
                  setCatalogError(
                     "No ready data sources are available for chat yet."
                  );
               }
               return;
            }

            if (!nextConnection?.isQueryReady) {
               setNamespaces([]);
               setEntities([]);
               setSelectedNamespace(undefined);
               setSelectedEntityId(undefined);
               setHasLoadedEntities(false);
               setCatalogError(
                  "Select a ready data source before choosing scope."
               );
               return;
            }

            const namespacesResult = await catalogService.listNamespaces(
               project.id,
               nextConnectionId
            );

            if (bootstrapRequestRef.current !== requestId) {
               return;
            }

            const nextNamespaces =
               namespacesResult.succeed && namespacesResult.data
                  ? namespacesResult.data
                  : [];
            setNamespaces(nextNamespaces);

            const nextNamespace = getDefaultNamespace(
               nextNamespaces,
               overrides.namespaceName ?? selectedNamespaceRef.current
            );
            setSelectedNamespace(nextNamespace);

            const shouldReloadEntities =
               hasLoadedEntities &&
               overrides.connectionId === undefined &&
               overrides.namespaceName === undefined &&
               selectedConnectionRef.current === nextConnectionId &&
               selectedNamespaceRef.current === nextNamespace;

            const connectionChanged =
               selectedConnectionRef.current !== nextConnectionId;
            const namespaceChanged =
               selectedNamespaceRef.current !== nextNamespace;

            if (connectionChanged || namespaceChanged || !nextNamespace) {
               entityRequestRef.current += 1;
               setEntities([]);
               setSelectedEntityId(undefined);
               setHasLoadedEntities(false);
            }

            if (shouldReloadEntities && nextNamespace) {
               await loadEntities(nextNamespace);
            }
         } finally {
            if (bootstrapRequestRef.current === requestId) {
               setIsCatalogLoading(false);
            }
         }
      },
      [
         catalogService,
         hasLoadedEntities,
         loadEntities,
         project.id,
         tokens?.accessToken
      ]
   );

   useEffect(() => {
      refreshCatalogScopeRef.current = refreshCatalogScope;
   }, [refreshCatalogScope]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void refreshCatalogScopeRef.current?.();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [catalogService, project.id, tokens?.accessToken]);

   const selectedConnection =
      connections.find(
         (connection) => connection.id === selectedConnectionId
      ) || null;
   const selectedEntity =
      entities.find((entity) => entity.id === selectedEntityId) || null;

   const hasScopeChoices =
      connections.length > 1 ||
      namespaces.length > 1 ||
      (hasLoadedEntities && entities.length > 0);

   const selectConnection = useCallback(
      async (connectionId: string) => {
         const connection = connections.find(
            (item) => item.id === connectionId
         );
         if (!connection?.isQueryReady) {
            setCatalogError("This data source is not ready for chat yet.");
            return;
         }
         setSelectedConnectionId(connectionId);
         setSelectedNamespace(undefined);
         setSelectedEntityId(undefined);
         setEntities([]);
         setHasLoadedEntities(false);
         await refreshCatalogScope({ connectionId });
      },
      [connections, refreshCatalogScope]
   );

   const selectNamespace = useCallback(
      async (namespaceName?: string) => {
         const currentNamespace = selectedNamespaceRef.current;
         if (currentNamespace !== namespaceName) {
            setSelectedNamespace(namespaceName);
            setSelectedEntityId(undefined);
            setEntities([]);
            setHasLoadedEntities(false);
         }
         await refreshCatalogScope({
            connectionId: selectedConnectionRef.current,
            namespaceName
         });
      },
      [refreshCatalogScope]
   );

   const selectEntity = useCallback((entityId?: string) => {
      setSelectedEntityId(entityId);
   }, []);

   const clearEntitySelection = useCallback(() => {
      setSelectedEntityId(undefined);
   }, []);

   return useMemo(
      () => ({
         connections,
         namespaces,
         entities,
         selectedConnectionId,
         selectedNamespace,
         selectedEntityId,
         selectedConnection,
         selectedEntity,
         isCatalogLoading,
         isEntitiesLoading,
         hasLoadedEntities,
         catalogError,
         hasScopeChoices,
         refreshCatalogScope,
         loadEntities,
         clearEntitySelection,
         selectConnection,
         selectNamespace,
         selectEntity
      }),
      [
         clearEntitySelection,
         connections,
         namespaces,
         entities,
         selectedConnectionId,
         selectedNamespace,
         selectedEntityId,
         selectedConnection,
         selectedEntity,
         isCatalogLoading,
         isEntitiesLoading,
         hasLoadedEntities,
         catalogError,
         hasScopeChoices,
         refreshCatalogScope,
         loadEntities,
         selectConnection,
         selectNamespace,
         selectEntity
      ]
   );
}
