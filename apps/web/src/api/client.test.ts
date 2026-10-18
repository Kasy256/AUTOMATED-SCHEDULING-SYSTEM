import { setAccessToken } from "@/lib/auth/session";
import { isApiError } from "@/lib/problem";

import { apiFetch, apiResponse, onSignedOut } from "./client";

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
const problem = (status: number) =>
  new Response(JSON.stringify({ title: "Nope", status }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });

describe("apiFetch", () => {
  beforeEach(() => {
    setAccessToken("t1");
    vi.stubGlobal("navigator", {
      locks: { request: (_: string, fn: () => unknown) => fn() },
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("apiResponse returns the raw response and refreshes once on 401", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/auth/refresh"))
          return Promise.resolve(
            ok({ access_token: "t2", expires_in: 900, organisation_id: "o1" }),
          );
        calls += 1;
        return Promise.resolve(
          calls === 1
            ? problem(401)
            : new Response("a,b\n1,2\n", {
                headers: { "Content-Type": "text/csv" },
              }),
        );
      }),
    );
    const res = await apiResponse("/api/v1/solution-versions/v1/export.csv");
    expect(await res.text()).toBe("a,b\n1,2\n");
    expect(calls).toBe(2);
  });

  it("sends the bearer token", async () => {
    const fetchMock = vi.fn<
      (url: string, init?: RequestInit) => Promise<Response>
    >(() => Promise.resolve(ok({ a: 1 })));
    vi.stubGlobal("fetch", fetchMock);
    expect(
      await apiFetch<{ a: number }>("/api/v1/resources", { method: "GET" }),
    ).toEqual({ a: 1 });
    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer t1");
  });

  it("retries the original request exactly once after a refresh", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const auth = new Headers(init?.headers).get("Authorization") ?? "";
        calls.push(`${init?.method ?? "GET"} ${url} ${auth}`);
        if (url.endsWith("/auth/refresh"))
          return Promise.resolve(
            ok({ access_token: "t2", token_type: "bearer", expires_in: 900 }),
          );
        return Promise.resolve(
          auth === "Bearer t2" ? ok({ saved: true }) : problem(401),
        );
      }),
    );
    const result = await apiFetch<{ saved: boolean }>("/api/v1/resources", {
      method: "POST",
      body: JSON.stringify({ name: "x" }),
    });
    expect(result).toEqual({ saved: true });
    expect(calls).toEqual([
      "POST /api/v1/resources Bearer t1",
      "POST /api/v1/auth/refresh ",
      "POST /api/v1/resources Bearer t2",
    ]);
  });

  it("signs out when the refresh fails and throws the 401", async () => {
    const signedOut = vi.fn();
    const off = onSignedOut(signedOut);
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(problem(401))),
    );
    const error: unknown = await apiFetch("/api/v1/resources").catch(
      (e: unknown) => e,
    );
    expect(isApiError(error) && error.status).toBe(401);
    expect(signedOut).toHaveBeenCalledTimes(1);
    off();
  });

  it("does not refresh on a failed login", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(problem(401)));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/v1/auth/login", { method: "POST" }).catch(
      () => undefined,
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns undefined for 204", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))),
    );
    expect(
      await apiFetch("/api/v1/resources/x", { method: "DELETE" }),
    ).toBeUndefined();
  });
});
