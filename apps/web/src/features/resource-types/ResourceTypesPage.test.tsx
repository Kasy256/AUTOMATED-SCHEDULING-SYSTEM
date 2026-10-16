import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { ResourceTypesPage } from "./ResourceTypesPage";

const lecturer = {
  id: "t1",
  key: "lecturer",
  name: "Lecturer",
  kind: "person",
  attribute_schema: {
    version: 1,
    attributes: [
      {
        key: "faculty",
        label: "Faculty",
        type: "string",
        required: false,
        enum_values: null,
      },
    ],
  },
};

function signedInAs(manage: boolean) {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedIn",
    me: null,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    can: (a) => (a === "config.manage" ? manage : true),
  });
}

describe("ResourceTypesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("creates a type with an attribute", async () => {
    signedInAs(true);
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posted.push(JSON.parse(init.body as string));
          return Promise.resolve(
            jsonResponse(
              {
                ...lecturer,
                id: "t2",
                key: "room",
                name: "Room",
                kind: "space",
              },
              201,
            ),
          );
        }
        return Promise.resolve(jsonResponse([lecturer]));
      }),
    );
    renderWithProviders(<ResourceTypesPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "New resource type" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "Room");
    await userEvent.clear(within(dialog).getByLabelText("Key"));
    await userEvent.type(within(dialog).getByLabelText("Key"), "room");
    await userEvent.selectOptions(
      within(dialog).getByLabelText("Kind"),
      "space",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add attribute" }),
    );
    await userEvent.type(
      within(dialog).getByLabelText("Attribute 1 key"),
      "room_type",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(posted).toEqual([
      {
        key: "room",
        name: "Room",
        kind: "space",
        attribute_schema: {
          version: 1,
          attributes: [
            {
              key: "room_type",
              label: null,
              type: "string",
              required: false,
              enum_values: null,
            },
          ],
        },
      },
    ]);
  });

  it("explains why a type in use cannot be deleted", async () => {
    signedInAs(true);
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) =>
        Promise.resolve(
          init?.method === "DELETE"
            ? new Response(
                JSON.stringify({
                  title: "Conflict",
                  status: 409,
                  detail: "3 resources use this type",
                }),
                {
                  status: 409,
                  headers: { "Content-Type": "application/problem+json" },
                },
              )
            : jsonResponse([lecturer]),
        ),
      ),
    );
    renderWithProviders(<ResourceTypesPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Lecturer" }),
    );
    await userEvent.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );
    expect(
      await screen.findByText(
        "Lecturer is still used: 3 resources use this type",
      ),
    ).toBeInTheDocument();
  });

  it("hides edit controls from viewers", async () => {
    signedInAs(false);
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([lecturer]))),
    );
    renderWithProviders(<ResourceTypesPage />);
    expect(await screen.findByText("Lecturer")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "New resource type" }),
    ).toBeNull();
  });
});
