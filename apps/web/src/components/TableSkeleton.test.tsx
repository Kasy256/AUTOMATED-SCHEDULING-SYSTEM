import { render, screen } from "@testing-library/react";

import { TableSkeleton } from "./TableSkeleton";

describe("TableSkeleton", () => {
  it("announces loading and draws placeholder rows", () => {
    render(<TableSkeleton rows={4} columns={3} label="Loading resources" />);
    const status = screen.getByRole("status", { name: "Loading resources" });
    expect(status.querySelectorAll("[data-skeleton-row]")).toHaveLength(4);
  });
});
