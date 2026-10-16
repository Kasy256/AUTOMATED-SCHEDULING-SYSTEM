import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse } from "@/test/render";

import { AuthProvider, useAuth } from "./AuthProvider";
import { setAccessToken } from "./session";

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

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span>status:{auth.status}</span>
      <span>org:{auth.me?.organisation_id ?? "-"}</span>
      <button onClick={() => void auth.switchOrganisation("o2")}>switch</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    setAccessToken(null);
    vi.stubGlobal("navigator", {
      locks: { request: (_: string, fn: () => unknown) => fn() },
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("restores the session from the refresh cookie", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/auth/refresh")
            ? jsonResponse({
                access_token: "t",
                token_type: "bearer",
                expires_in: 900,
              })
            : jsonResponse(me("o1")),
        ),
      ),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("status:signedIn")).toBeInTheDocument();
    expect(screen.getByText("org:o1")).toBeInTheDocument();
  });

  it("is signed out when there is no refresh cookie", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("status:signedOut")).toBeInTheDocument();
  });

  it("clears the query cache on organisation switch", async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(["/api/v1/resources"], [{ id: "from-org-1" }]);
    let current = "o1";
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/auth/switch-organisation")) current = "o2";
        if (url.endsWith("/auth/me"))
          return Promise.resolve(jsonResponse(me(current)));
        return Promise.resolve(
          jsonResponse({
            access_token: "t",
            token_type: "bearer",
            expires_in: 900,
          }),
        );
      }),
    );
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    );
    await screen.findByText("org:o1");
    await userEvent.click(screen.getByText("switch"));
    await waitFor(() => {
      expect(screen.getByText("org:o2")).toBeInTheDocument();
    });
    expect(queryClient.getQueryData(["/api/v1/resources"])).toBeUndefined();
  });
});
