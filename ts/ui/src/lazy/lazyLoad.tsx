import React, {
   type ComponentType,
   type LazyExoticComponent,
   Suspense
} from "react";
import { LoadingSpinner } from "../components";

export const withSuspense = (
   Component: ComponentType | LazyExoticComponent<ComponentType>
) => (
   <Suspense fallback={<LoadingSpinner />}>
      <Component />
   </Suspense>
);

export const createPreloadableLazyWithProps = <P extends object>(
   importFunc: () => Promise<{ default: ComponentType<P> }>
) => {
   const LazyComponent = React.lazy(importFunc);

   const LazyComponentWithPreload = LazyComponent as typeof LazyComponent & {
      preload: typeof importFunc;
   };
   LazyComponentWithPreload.preload = importFunc;

   return LazyComponentWithPreload;
};
