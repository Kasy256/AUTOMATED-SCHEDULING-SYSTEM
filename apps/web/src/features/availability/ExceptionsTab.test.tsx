import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { ExceptionsTab } from "./ExceptionsTab";

describe("ExceptionsTab", () => {
  beforeEach(() => {
    vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
      ...new Intl.DateTimeFormat("en-GB", {
        timeZone: "Africa/Kampala",
      }).resolvedOptions(),
      timeZone: "Africa/Kampala",
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends exceptions as UTC instants", async () => {
    const posted: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          posted.push(JSON.parse(init.body as string));
          return Promise.resolve(
            jsonResponse({ id: "e1", resource_id: "r1" }, 201),
          );
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );
    renderWithProviders(<ExceptionsTab resourceId="r1" canEdit />);
    await userEvent.selectOptions(
      await screen.findByLabelText("Kind"),
      "unavailable",
    );
    await userEvent.type(screen.getByLabelText("From"), "2026-03-02T09:00");
    await userEvent.type(screen.getByLabelText("To"), "2026-03-02T12:00");
    await userEvent.type(screen.getByLabelText("Reason"), "Conference");
    await userEvent.click(
      screen.getByRole("button", { name: "Add exception" }),
    );
    await vi.waitFor(() => {
      expect(posted).toEqual([
        {
          kind: "unavailable",
          starts_at: "2026-03-02T06:00:00.000Z",
          ends_at: "2026-03-02T09:00:00.000Z",
          reason: "Conference",
        },
      ]);
    });
  });

  it("rejects an end before the start", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(jsonResponse([])),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<ExceptionsTab resourceId="r1" canEdit />);
    await userEvent.type(
      await screen.findByLabelText("From"),
      "2026-03-02T12:00",
    );
    await userEvent.type(screen.getByLabelText("To"), "2026-03-02T09:00");
    await userEvent.click(
      screen.getByRole("button", { name: "Add exception" }),
    );
    expect(
      await screen.findByText("End must be after start"),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);
  });
});
