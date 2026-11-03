import "@testing-library/jest-dom";

class ResizeObserverMock {
   observe() {}
   unobserve() {}
   disconnect() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
   writable: true,
   value: ResizeObserverMock
});

Object.defineProperty(globalThis, "matchMedia", {
   writable: true,
   value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false
   })
});
