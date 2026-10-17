import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// Rendering + query resolution can exceed the 1 s default on slow machines.
configure({ asyncUtilTimeout: 5000 });

// jsdom lacks ResizeObserver; Radix measures some controls (switch, popover) with it.
globalThis.ResizeObserver = class {
  observe(): void {
    // nothing to measure in jsdom
  }
  unobserve(): void {
    // nothing to measure in jsdom
  }
  disconnect(): void {
    // nothing to measure in jsdom
  }
};

// jsdom lacks scrollIntoView; cmdk scrolls the highlighted option into view.
Element.prototype.scrollIntoView = function scrollIntoView() {
  // nothing to scroll in jsdom
};
