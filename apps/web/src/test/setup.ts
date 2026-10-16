import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// Rendering + query resolution can exceed the 1 s default on slow machines.
configure({ asyncUtilTimeout: 5000 });
