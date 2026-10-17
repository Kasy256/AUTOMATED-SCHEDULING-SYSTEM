import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { MembersPage } from "./MembersPage";

const members = [
  {
    membership_id: "m1",
    user_id: "u1",
    email: "ada@example.com",
    name: "Ada",
    status: "active",
    roles: ["org_admin"],
  },
  {
    membership_id: "m2",
    user_id: "u2",
    email: "ben@example.com",
    name: "Ben",
    status: "invited",
    roles: ["viewer"],
  },
];

function signedIn() {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedIn",
    me: null,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    adoptSession: vi.fn(),
    can: () => true,
  });
}

const problem = (status: number, detail: string) =>
  new Response(JSON.stringify({ title: "Conflict", status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });

describe("MembersPage", () => {
  beforeEach(signedIn);
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists members with roles and status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(members))),
    );
    renderWithProviders(<MembersPage />);
    const row = (await screen.findByText("Ada")).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Invited")).toBeInTheDocument();
  });

  it("invites a member with chosen roles", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posted.push(JSON.parse(init.body as string));
          return Promise.resolve(jsonResponse({}, 201));
        }
        return Promise.resolve(jsonResponse(members));
      }),
    );
    renderWithProviders(<MembersPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Invite member" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(
      within(dialog).getByLabelText("Email"),
      "cy@example.com",
    );
    await userEvent.type(within(dialog).getByLabelText("Name"), "Cy");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    expect(
      await within(dialog).findByText("Choose at least one role"),
    ).toBeInTheDocument();
    expect(posted).toEqual([]);
    await userEvent.click(within(dialog).getByLabelText("Planner"));
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Send invitation" }),
    );
    await vi.waitFor(() => {
      expect(posted).toEqual([
        { email: "cy@example.com", name: "Cy", roles: ["planner"] },
      ]);
    });
  });

  it("explains the last-admin rule and keeps the dialog open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) =>
        Promise.resolve(
          init?.method === "PUT"
            ? problem(409, "The last org admin cannot be removed")
            : jsonResponse(members),
        ),
      ),
    );
    renderWithProviders(<MembersPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit roles of Ada" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByLabelText("Admin"));
    await userEvent.click(within(dialog).getByLabelText("Planner"));
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Save roles" }),
    );
    expect(
      await within(dialog).findByText(
        "An organisation needs at least one admin.",
      ),
    ).toBeInTheDocument();
  });
});
