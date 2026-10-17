import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { ExplanationPanel } from "./ExplanationPanel";

const item = {
  activityId: "a1",
  name: "CS 201",
  start: "2026-01-12T06:00:00.000Z",
  resources: { lecturer: ["L1"], room: ["R1"] },
  pending: false,
  pinned: false,
};
const valid = {
  start_at: "2026-01-13T06:00:00Z",
  resources: { lecturer: ["L1"], room: ["R2"] },
  check: { valid: true, broken: [], penalties: [] },
};
const invalid = {
  start_at: "2026-01-14T06:00:00Z",
  resources: { lecturer: ["L1"], room: ["R1"] },
  check: {
    valid: false,
    broken: [
      {
        constraint_id: "c2",
        rule: "Room free",
        message: "Room LH3 is busy",
        activity_ids: [],
        resource_ids: [],
      },
    ],
    penalties: [],
  },
};
const explanation = {
  activity_id: "a1",
  binding: [
    {
      constraint_id: "c1",
      rule: "At most 2 activities per day",
      hard: true,
      blocks: 3,
      penalises: 0,
    },
  ],
  alternatives: [valid, invalid],
  truncated: false,
};

function api() {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.includes("/explanation"))
        return Promise.resolve(jsonResponse(explanation));
      if (url.includes("/pins/a1"))
        return Promise.resolve(
          jsonResponse({
            activity_id: "a1",
            start_at: item.start,
            resources: item.resources,
          }),
        );
      return Promise.resolve(jsonResponse([]));
    }),
  );
  return calls;
}

function panel(canEdit: boolean, onMoveHere = vi.fn()) {
  renderWithProviders(
    <ExplanationPanel
      scheduleId="s1"
      versionId="v1"
      item={item}
      rowId="L1"
      editable
      canEdit={canEdit}
      columnLabel={(start) => start.slice(0, 10)}
      codeOf={(id) => ({ R1: "LH3", R2: "LH4", L1: "L001" })[id] ?? id}
      onClose={vi.fn()}
      onMoveHere={onMoveHere}
    />,
  );
  return onMoveHere;
}

describe("ExplanationPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("explains, lists alternatives and moves here", async () => {
    api();
    const onMoveHere = panel(true);
    expect(
      await screen.findByText("At most 2 activities per day"),
    ).toBeInTheDocument();
    expect(screen.getByText("Blocks 3 alternatives")).toBeInTheDocument();
    expect(screen.getByText("Valid")).toBeInTheDocument();
    expect(screen.getByText("Room LH3 is busy")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Move here" }));
    expect(onMoveHere).toHaveBeenCalledWith({
      activity_id: "a1",
      start_at: valid.start_at,
      resources: valid.resources,
    });
  });

  it("pins the current placement", async () => {
    const calls = api();
    panel(true);
    await userEvent.click(await screen.findByRole("button", { name: "Pin" }));
    const put = calls.find((c) => c.init?.method === "PUT");
    expect(put?.url).toContain("/api/v1/schedules/s1/pins/a1");
    expect(JSON.parse(put?.init?.body as string)).toEqual({
      start_at: item.start,
      resources: item.resources,
    });
  });

  it("viewers get a read-only panel", async () => {
    api();
    panel(false);
    expect(
      await screen.findByText("At most 2 activities per day"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pin" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Move here" })).toBeNull();
  });
});
