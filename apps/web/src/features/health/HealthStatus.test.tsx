import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthStatus } from "./HealthStatus";

function renderWithQuery() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <HealthStatus />
    </QueryClientProvider>,
  );
}

function stubFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        }),
      ),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HealthStatus", () => {
  it("shows the database role when healthy", async () => {
    stubFetch(200, {
      status: "ok",
      database: {
        current_user: "cartlyf_app",
        rolsuper: false,
        rolbypassrls: false,
      },
    });
    renderWithQuery();
    expect(
      await screen.findByText(/connected as cartlyf_app/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/superuser: no/i)).toBeInTheDocument();
    expect(screen.getByText(/bypassrls: no/i)).toBeInTheDocument();
  });

  it("shows the problem title when unhealthy", async () => {
    stubFetch(503, {
      type: "about:blank",
      title: "Unsafe database role",
      status: 503,
    });
    renderWithQuery();
    expect(
      await screen.findByText(/unsafe database role/i),
    ).toBeInTheDocument();
  });

  it("shows the HTTP status when an error response has no problem body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 500 }))),
    );
    renderWithQuery();
    expect(
      await screen.findByText(/api error \(http 500\)/i),
    ).toBeInTheDocument();
  });

  it("says the API is unreachable when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    renderWithQuery();
    expect(await screen.findByText(/api unreachable/i)).toBeInTheDocument();
  });
});
