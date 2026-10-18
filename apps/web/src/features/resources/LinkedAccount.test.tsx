import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { LinkedAccount } from "./LinkedAccount";

const resource = {
  id: "R1",
  resource_type_id: "t1",
  code: "L001",
  name: "Kato",
  tags: [],
  attributes: {},
  capacity: null,
  size: null,
  concurrency: 1,
  user_id: null,
};
const member = (user: string, name: string, status = "active") => ({
  membership_id: `m-${user}`,
  user_id: user,
  email: `${name.toLowerCase()}@example.com`,
  name,
  status,
  roles: ["member"],
});

describe("LinkedAccount", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("links a member's account to the resource", async () => {
    const patches: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          patches.push({
            url,
            body: JSON.parse(init.body as string) as unknown,
          });
          return Promise.resolve(jsonResponse({ ...resource, user_id: "u2" }));
        }
        return Promise.resolve(
          jsonResponse([member("u2", "Amina"), member("u3", "Old", "invited")]),
        );
      }),
    );
    renderWithProviders(<LinkedAccount resource={resource} />);
    const select = await screen.findByLabelText("Linked account");
    expect(
      await screen.findByRole("option", { name: "Amina (amina@example.com)" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Old/ })).toBeNull();
    await userEvent.selectOptions(select, "u2");
    await vi.waitFor(() => {
      expect(patches).toEqual([
        { url: "/api/v1/resources/R1", body: { user_id: "u2" } },
      ]);
    });
  });
});
