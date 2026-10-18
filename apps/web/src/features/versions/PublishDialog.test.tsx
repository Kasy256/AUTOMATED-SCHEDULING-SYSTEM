import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { ArchiveButton, PublishButton } from "./PublishDialog";

// The dialog's button shares its name with the button that opened it.
function lastButton(name: string): HTMLElement {
  const all = screen.getAllByRole("button", { name });
  const last = all[all.length - 1];
  if (!last) throw new Error(`no ${name} button`);
  return last;
}

const summary = (
  number: number,
  status: "draft" | "published" | "archived",
) => ({
  id: `v${String(number)}`,
  schedule_id: "s1",
  number,
  status,
  solver_status: "OPTIMAL",
  hard_violations: 0,
  soft_total: 0,
  created_at: "2026-01-01T00:00:00Z",
  published_at: null,
  archived_at: null,
  parent_version_id: null,
  solve_run_id: `r${String(number)}`,
});
const change = { activity_id: "a1", before: null, after: null };

function api() {
  const posts: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") posts.push(url);
      if (url.includes("/diff/"))
        return Promise.resolve(
          jsonResponse({
            added: [],
            removed: [],
            moved: [change, change],
            reassigned: [change],
          }),
        );
      if (url.endsWith("/publish"))
        return Promise.resolve(jsonResponse({ ...summary(3, "published") }));
      if (url.endsWith("/archive"))
        return Promise.resolve(jsonResponse({ ...summary(3, "archived") }));
      return Promise.resolve(jsonResponse([]));
    }),
  );
  return posts;
}

describe("publish and archive", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the change summary and publishes", async () => {
    const posts = api();
    const versions = [
      summary(2, "published"),
      summary(3, "draft"),
      summary(4, "draft"),
    ];
    renderWithProviders(
      <PublishButton
        version={summary(3, "draft")}
        versions={versions}
        scheduleId="s1"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      await screen.findByText("2 moved · 1 reassigned · 0 added · 0 removed"),
    ).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Version 3 is not the newest version.");
    expect(
      screen.getByRole("link", { name: "See all changes" }),
    ).toHaveAttribute("href", "/schedules/s1/versions/v2/compare/v3");
    await userEvent.click(lastButton("Publish"));
    await vi.waitFor(() => {
      expect(posts).toContain("/api/v1/solution-versions/v3/publish");
    });
  });

  it("archives after confirmation", async () => {
    const posts = api();
    renderWithProviders(
      <ArchiveButton version={summary(3, "draft")} scheduleId="s1" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(await screen.findByText("Archive version 3?")).toBeInTheDocument();
    await userEvent.click(lastButton("Archive"));
    await vi.waitFor(() => {
      expect(posts).toContain("/api/v1/solution-versions/v3/archive");
    });
  });
});
