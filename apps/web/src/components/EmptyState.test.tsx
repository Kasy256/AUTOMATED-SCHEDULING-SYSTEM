import { render, screen } from "@testing-library/react";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows a decorative illustration with the message", () => {
    const { container } = render(
      <EmptyState
        illustration="empty"
        title="No rules yet"
        description="Add one."
      />,
    );
    expect(
      screen.getByRole("heading", { name: "No rules yet" }),
    ).toBeInTheDocument();
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("alt", "");
    expect(img).toHaveAttribute("aria-hidden", "true");
  });
});
