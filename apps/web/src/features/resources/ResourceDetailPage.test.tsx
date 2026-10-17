import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { ResourceDetailPage } from "./ResourceDetailPage";

const resource = {
  id: "r1",
  resource_type_id: "t1",
  code: "L005",
  name: "Dr. Okello",
  tags: ["cs"],
  attributes: { faculty: "CS" },
  capacity: null,
  size: null,
  concurrency: 1,
  user_id: null,
};
const type = {
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
        required: true,
        enum_values: null,
      },
      {
        key: "max_hours",
        label: null,
        type: "integer",
        required: false,
        enum_values: null,
      },
    ],
  },
};

describe("ResourceDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("validates typed attributes before saving", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      adoptSession: vi.fn(),
      can: () => true,
    });
    const patches: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          patches.push(JSON.parse(init.body as string));
          return Promise.resolve(jsonResponse(resource));
        }
        if (url.includes("/resource-types/"))
          return Promise.resolve(jsonResponse(type));
        if (url.includes("/availability"))
          return Promise.resolve(jsonResponse([]));
        return Promise.resolve(jsonResponse(resource));
      }),
    );
    renderWithProviders(<ResourceDetailPage />, {
      route: "/resources/r1",
      path: "/resources/:resourceId",
    });
    expect(await screen.findByLabelText("Faculty")).toHaveValue("CS");
    await userEvent.type(screen.getByLabelText("max_hours"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Enter a whole number")).toBeInTheDocument();
    expect(patches).toEqual([]);

    await userEvent.clear(screen.getByLabelText("max_hours"));
    await userEvent.type(screen.getByLabelText("max_hours"), "20");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await vi.waitFor(() => {
      expect(patches).toHaveLength(1);
    });
    expect(patches[0]).toMatchObject({
      attributes: { faculty: "CS", max_hours: 20 },
    });
  });
});
