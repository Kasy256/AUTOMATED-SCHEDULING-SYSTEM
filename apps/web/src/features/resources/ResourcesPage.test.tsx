import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { filterResources } from "./filter";
import { ResourcesPage } from "./ResourcesPage";

const types = [
  {
    id: "t1",
    key: "lecturer",
    name: "Lecturer",
    kind: "person",
    attribute_schema: { version: 1, attributes: [] },
  },
  {
    id: "t2",
    key: "room",
    name: "Room",
    kind: "space",
    attribute_schema: { version: 1, attributes: [] },
  },
];
const resources = [
  {
    id: "r1",
    resource_type_id: "t1",
    code: "L005",
    name: "Dr. Okello",
    tags: ["cs"],
    attributes: {},
    capacity: null,
    size: null,
    concurrency: 1,
    user_id: null,
  },
  {
    id: "r2",
    resource_type_id: "t2",
    code: "LH3",
    name: "Lecture Hall 3",
    tags: [],
    attributes: {},
    capacity: 120,
    size: null,
    concurrency: 1,
    user_id: null,
  },
];

describe("filterResources", () => {
  it("filters by type and by code, name or tag", () => {
    expect(
      filterResources(resources, { typeId: "t2", query: "" }).map((r) => r.id),
    ).toEqual(["r2"]);
    expect(
      filterResources(resources, { typeId: "all", query: "okel" }).map(
        (r) => r.id,
      ),
    ).toEqual(["r1"]);
    expect(
      filterResources(resources, { typeId: "all", query: "CS" }).map(
        (r) => r.id,
      ),
    ).toEqual(["r1"]);
  });
});

describe("ResourcesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows one tab per type and links rows to the detail page", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      can: () => true,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          jsonResponse(url.includes("resource-types") ? types : resources),
        ),
      ),
    );
    renderWithProviders(<ResourcesPage />);
    await userEvent.click(await screen.findByRole("tab", { name: "Room" }));
    expect(
      screen.getByRole("link", { name: "Lecture Hall 3" }),
    ).toHaveAttribute("href", "/resources/r2");
    expect(screen.queryByText("Dr. Okello")).toBeNull();
  });
  it("shows a loading skeleton instead of an empty table", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      can: () => true,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    renderWithProviders(<ResourcesPage />);
    expect(
      await screen.findByRole("status", { name: "Loading resources" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Name" })).toBeNull();
  });
});
