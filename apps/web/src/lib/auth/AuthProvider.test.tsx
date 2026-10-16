import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";

import { jsonResponse } from "@/test/render";

import { AuthProvider, useAuth } from "./AuthProvider";
import { refreshAccessToken, setAccessToken } from "./session";

const me = (org: string) => ({
  user_id: "u1",
  email: "a@b.c",
  name: "Ada",
  organisation_id: org,
  roles: ["org_admin"],
  platform_admin_session: false,
  organisations: [
    { organisation_id: "o1", name: "One" },
    { organisation_id: "o2", name: "Two" },
  ],
});
const token = (org: string) => ({
  access_token: `t-${org}`,
  token_type: "bearer",
  expires_in: 900,
  organisation_id: org,
});

function Probe() {
  const auth = useAuth();
  const location = useLocation();
  return (
    <div>
      <span>status:{auth.status}</span>
      <span>org:{auth.me?.organisation_id ?? "-"}</span>
      <span>path:{location.pathname}</span>
      <button onClick={() => void auth.switchOrganisation("o2")}>switch</button>
      <button onClick={() => void auth.login("a@b.c", "pw")}>login</button>
    </div>
  );
}

function mount(queryClient = new QueryClient(), route = "/") {
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return queryClient;
}

// The server keeps the active organisation with the refresh cookie; `current` plays that role.
function serverAt(
  start: string,
  onFetch?: (url: string, held: boolean) => void,
) {
  const state = { current: start, held: false };
  vi.stubGlobal("navigator", {
    locks: {
      request: async (_: string, fn: () => Promise<unknown>) => {
        state.held = true;
        try {
          return await fn();
        } finally {
          state.held = false;
        }
      },
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      onFetch?.(url, state.held);
      if (url.endsWith("/auth/switch-organisation")) state.current = "o2";
      if (url.endsWith("/auth/me"))
        return Promise.resolve(jsonResponse(me(state.current)));
      return Promise.resolve(jsonResponse(token(state.current)));
    }),
  );
  return state;
}

describe("AuthProvider", () => {
  beforeEach(() => {
    setAccessToken(null);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("restores the session from the refresh cookie", async () => {
    serverAt("o1");
    mount();
    expect(await screen.findByText("status:signedIn")).toBeInTheDocument();
    expect(screen.getByText("org:o1")).toBeInTheDocument();
  });

  it("is signed out when there is no refresh cookie", async () => {
    vi.stubGlobal("navigator", {
      locks: { request: (_: string, fn: () => unknown) => fn() },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );
    mount();
    expect(await screen.findByText("status:signedOut")).toBeInTheDocument();
  });

  it("clears the cache and goes home on organisation switch", async () => {
    serverAt("o1");
    const queryClient = mount(new QueryClient(), "/schedules/s-of-o1/rules");
    queryClient.setQueryData(["/api/v1/resources"], [{ id: "from-org-1" }]);
    await screen.findByText("org:o1");
    await userEvent.click(screen.getByText("switch"));
    await waitFor(() => {
      expect(screen.getByText("org:o2")).toBeInTheDocument();
    });
    expect(screen.getByText("path:/")).toBeInTheDocument();
    expect(queryClient.getQueryData(["/api/v1/resources"])).toBeUndefined();
  });

  it("switches inside the session lock so a concurrent refresh can't spend the same cookie", async () => {
    const heldDuringSwitch: boolean[] = [];
    serverAt("o1", (url, held) => {
      if (url.endsWith("/auth/switch-organisation"))
        heldDuringSwitch.push(held);
    });
    mount();
    await screen.findByText("org:o1");
    await userEvent.click(screen.getByText("switch"));
    await waitFor(() => {
      expect(heldDuringSwitch).toEqual([true]);
    });
  });

  it("follows an organisation change made in another tab", async () => {
    const server = serverAt("o1");
    const queryClient = mount(new QueryClient(), "/resources");
    await screen.findByText("org:o1");
    queryClient.setQueryData(["/api/v1/resources"], [{ id: "from-org-1" }]);
    server.current = "o2"; // another tab switched; this tab's next refresh gets an o2 token
    await refreshAccessToken();
    await waitFor(() => {
      expect(screen.getByText("org:o2")).toBeInTheDocument();
    });
    expect(screen.getByText("path:/")).toBeInTheDocument();
    expect(queryClient.getQueryData(["/api/v1/resources"])).toBeUndefined();
  });

  it("clears the previous session's cache on login", async () => {
    serverAt("o1");
    const queryClient = mount();
    await screen.findByText("org:o1");
    queryClient.setQueryData(["/api/v1/resources"], [{ id: "someone-else" }]);
    await userEvent.click(screen.getByText("login"));
    await waitFor(() => {
      expect(queryClient.getQueryData(["/api/v1/resources"])).toBeUndefined();
    });
  });
});
