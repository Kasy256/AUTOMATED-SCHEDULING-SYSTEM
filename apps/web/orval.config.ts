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
    },
  },
});
