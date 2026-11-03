import type { DataRef, DataTable } from "@kontext-tech/schema";
import { useEffect, useState, useMemo } from "react";
import { useNotebookServices } from "../context/NotebookServiceContext";

const dataCache = new Map<string, DataTable>();
const promiseCache = new Map<string, Promise<DataTable | undefined>>();
const listeners = new Set<(key: string | null) => void>();

export function invalidateNotebookDataCache(dataId?: string) {
   if (dataId) {
      for (const key of dataCache.keys()) {
         if (key.includes(`"dataId":"${dataId}"`)) {
            dataCache.delete(key);
            promiseCache.delete(key);
         }
      }
      listeners.forEach((l) => l(dataId));
   } else {
      dataCache.clear();
      promiseCache.clear();
      listeners.forEach((l) => l(null));
   }
}

/**
 * Resolves notebook data from either notebook-managed resources or
 * externally referenced sources exposed by the host app.
 * Uses a lightweight module-level cache since react-query was removed.
 */
export function useNotebookDataReference(dataRef?: DataRef): {
   data: DataTable | undefined;
   isLoading: boolean;
   error: Error | null;
} {
   const { fileSystem, projectId, dataResolver } = useNotebookServices();

   // Memoize stringified dataRef to prevent unnecessary useEffect triggers
   const serializedRef = useMemo(
      () => (dataRef ? JSON.stringify(dataRef) : null),
      [dataRef]
   );

   const cacheKey = dataRef ? `data-${serializedRef}-${projectId}` : null;

   const [state, setState] = useState<{
      data: DataTable | undefined;
      isLoading: boolean;
      error: Error | null;
   }>({
      data: cacheKey ? dataCache.get(cacheKey) : undefined,
      isLoading: !!dataRef && (!cacheKey || !dataCache.has(cacheKey)),
      error: null
   });

   useEffect(() => {
      if (!dataRef || !cacheKey) {
         return;
      }

      let isMounted = true;

      const fetchData = async () => {
         if (dataRef.dataId && fileSystem?.getInlineData) {
            const res = await fileSystem.getInlineData(
               dataRef.dataId,
               projectId
            );

            if (res.succeed && res.data) {
               return res.data;
            }
         }

         if (dataResolver?.resolveData) {
            const res = await dataResolver.resolveData(dataRef, projectId);

            if (res.succeed && res.data) {
               return res.data;
            }

            throw new Error(
               res.error?.messages.join(", ") ||
                  "Failed to resolve external data reference",
               { cause: res.error }
            );
         }

         throw new Error(
            "No notebook data resolver is available for this reference"
         );
      };

      const load = () => {
         if (dataCache.has(cacheKey)) {
            setState({
               data: dataCache.get(cacheKey),
               isLoading: false,
               error: null
            });
            return;
         }
         setState((prev) => ({ ...prev, isLoading: true, error: null }));

         if (!promiseCache.has(cacheKey)) {
            let retries = 3;
            const attemptFetch = async (): Promise<DataTable | undefined> => {
               try {
                  return await fetchData();
               } catch (err) {
                  if (retries > 0) {
                     retries--;
                     await new Promise((r) =>
                        setTimeout(r, Math.min(1000 * 2 ** (3 - retries), 3000))
                     );
                     return attemptFetch();
                  }
                  throw err;
               }
            };

            const promise = attemptFetch()
               .then((data) => {
                  if (data) dataCache.set(cacheKey, data);
                  return data;
               })
               .catch((err) => {
                  promiseCache.delete(cacheKey); // clear failed promises
                  throw err;
               });
            promiseCache.set(cacheKey, promise);
         }

         promiseCache
            .get(cacheKey)!
            .then((data) => {
               if (isMounted) setState({ data, isLoading: false, error: null });
            })
            .catch((error) => {
               if (isMounted)
                  setState({
                     data: undefined,
                     error: error as Error,
                     isLoading: false
                  });
            });
      };

      load();

      const listener = (invalidatedDataId: string | null) => {
         if (
            !invalidatedDataId ||
            (dataRef.dataId && invalidatedDataId === dataRef.dataId)
         ) {
            load();
         }
      };

      listeners.add(listener);

      return () => {
         isMounted = false;
         listeners.delete(listener);
      };
   }, [serializedRef, projectId, fileSystem, dataResolver, cacheKey, dataRef]);

   return state;
}

export function useNotebookInlineData(dataIdOrRef?: string | DataRef): {
   data: DataTable | undefined;
   isLoading: boolean;
   error: Error | null;
} {
   const dataRef = useMemo(
      () =>
         typeof dataIdOrRef === "string"
            ? { dataId: dataIdOrRef }
            : dataIdOrRef,
      [dataIdOrRef]
   );

   return useNotebookDataReference(dataRef);
}
