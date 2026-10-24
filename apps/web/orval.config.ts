import { defineConfig } from "orval";

export default defineConfig({
  cartlyf: {
    input: "./openapi.json",
    output: {
      mode: "tags-split",
      target: "src/api/generated",
      schemas: "src/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      clean: true,
      override: {
        mutator: { path: "./src/api/client.ts", name: "apiFetch" },
        // Generated functions return the success body; errors arrive as thrown ApiError.
        fetch: { includeHttpResponseReturnType: false },
        query: { version: 5 },
      },
    },
  },
});
