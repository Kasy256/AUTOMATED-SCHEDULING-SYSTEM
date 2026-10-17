import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithProviders } from "@/test/render";

import { ScorePanel } from "./ScorePanel";

const rule = (id: string, name: string) => ({
  id,
  schedule_id: "s1",
  template_key: "t",
  name,
  hard: false,
  weight: 1,
  params: {},
  scope: {},
  summary: "",
});

describe("ScorePanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("breaks the soft penalty down by rule, largest first", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse([
            rule("c1", "Keep days compact"),
            rule("c2", "Lecturer load (soft)"),
          ]),
        ),
      ),
    );
    renderWithProviders(
      <ScorePanel
        scheduleId="s1"
        score={{
          hard_violations: 0,
          soft_total: 50,
          terms: [
            { constraint_id: "c2", penalty: 40, details: "Kato teaches 5" },
            { constraint_id: "c1", penalty: 10 },
          ],
        }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Score" }));
    expect(await screen.findByText("Soft penalty: 50")).toBeInTheDocument();
    expect(screen.getByText("Hard rules broken: 0")).toBeInTheDocument();
    const [first, second] = (await screen.findAllByRole("listitem")).map((li) =>
      within(li),
    );
    expect(first?.getByText("Lecturer load (soft)")).toBeInTheDocument();
    expect(first?.getByText("40")).toBeInTheDocument();
    expect(second?.getByText("Keep days compact")).toBeInTheDocument();
    expect(second?.getByText("10")).toBeInTheDocument();
  });

  it("says when every preference is met", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))),
    );
    renderWithProviders(
      <ScorePanel
        scheduleId="s1"
        score={{ hard_violations: 0, soft_total: 0 }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Score" }));
    expect(
      await screen.findByText("No soft penalties — every preference is met."),
    ).toBeInTheDocument();
  });
});
