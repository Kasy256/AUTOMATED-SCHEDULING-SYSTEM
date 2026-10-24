import { apiUrl } from "./base";

describe("apiUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("keeps the path when no API base URL is configured", () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    expect(apiUrl("/api/v1/auth/me")).toBe("/api/v1/auth/me");
  });

  it("prefixes the configured API host, ignoring a trailing slash", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/");
    expect(apiUrl("/api/v1/auth/me")).toBe(
      "https://api.example.test/api/v1/auth/me",
    );
  });
});
