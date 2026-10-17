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

// jsdom has no layout, so every element measures 0×0; the planner's virtualised grid
// would then render no rows. Give elements a desktop-sized box instead.
Object.defineProperties(HTMLElement.prototype, {
  clientWidth: { configurable: true, get: () => 1200 },
  clientHeight: { configurable: true, get: () => 800 },
});
