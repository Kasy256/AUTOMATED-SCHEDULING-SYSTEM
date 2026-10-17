import { getAccessToken, refreshAccessToken, setAccessToken } from "./session";

const tokenResponse = (token: string) =>
  new Response(
    JSON.stringify({
      access_token: token,
      token_type: "bearer",
      expires_in: 900,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );

describe("refreshAccessToken", () => {
  let lockNames: string[];

  beforeEach(() => {
    setAccessToken(null);
    lockNames = [];
    let tail = Promise.resolve();
    // A serialising fake of the Web Locks API, standing in for another tab's queue.
    vi.stubGlobal("navigator", {
      locks: {
        request: (name: string, fn: () => Promise<unknown>) => {
          lockNames.push(name);
          const run = tail.then(fn);
          tail = run.then(
            () => undefined,
            () => undefined,
          );
          return run;
        },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serialises refresh through the lock and reuses a fresh token", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(tokenResponse("new-token")));
    vi.stubGlobal("fetch", fetchMock);
    const [a, b] = await Promise.all([
      refreshAccessToken(),
      refreshAccessToken(),
    ]);
    expect(a).toBe("new-token");
    expect(b).toBe("new-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(lockNames).toEqual(["cartlyf-refresh"]);
    expect(getAccessToken()).toBe("new-token");
  });

  it("clears the token when the refresh is refused", async () => {
    setAccessToken("old");
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );
    expect(await refreshAccessToken()).toBeNull();
    expect(getAccessToken()).toBeNull();
  });
});
