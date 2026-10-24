import * as Sentry from "@sentry/react";
import type { ErrorEvent } from "@sentry/react";

import { initSentry, scrubEvent } from "./sentry";

vi.mock("@sentry/react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@sentry/react")>()),
  init: vi.fn(),
}));

describe("scrubEvent", () => {
  it("drops the user, cookies, headers and query strings", () => {
    const event = {
      type: undefined,
      user: { email: "a@example.com" },
      request: {
        url: "https://app.example.test/accept-invitation?token=abc",
        cookies: { cartlyf_refresh: "r" },
        headers: { Authorization: "Bearer t" },
        query_string: "token=abc",
      },
      breadcrumbs: [
        {
          category: "fetch",
          data: { url: "https://api.example.test/api/v1/x?token=abc" },
        },
      ],
    } as ErrorEvent;
    const out = JSON.stringify(scrubEvent(event));
    for (const secret of ["a@example.com", "Bearer t", "token=abc", '"r"']) {
      expect(out).not.toContain(secret);
    }
    expect(out).toContain("https://app.example.test/accept-invitation");
  });
});

describe("initSentry", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.mocked(Sentry.init).mockClear();
  });

  it("does nothing without a DSN", () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    initSentry();
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it("initialises without PII, tagged with environment and release", () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://k@o0.ingest.sentry.io/0");
    vi.stubEnv("VITE_DEPLOY_ENV", "staging");
    vi.stubEnv("VITE_RELEASE", "abc123");
    initSentry();
    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://k@o0.ingest.sentry.io/0",
        environment: "staging",
        release: "abc123",
      }),
    );
    const options = vi.mocked(Sentry.init).mock.calls[0]?.[0];
    expect(options?.dataCollection?.userInfo).toBe(false);
    expect(options?.dataCollection?.httpBodies).toEqual([]);
  });
});
