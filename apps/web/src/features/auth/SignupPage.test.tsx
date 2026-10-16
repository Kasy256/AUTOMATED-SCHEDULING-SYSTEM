import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "@/test/render";

import { SignupPage } from "./SignupPage";

describe("SignupPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("always ends at check-your-email", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 202 }))),
    );
    renderWithProviders(<SignupPage />, { route: "/signup" });
    await userEvent.type(screen.getByLabelText("Organisation name"), "ISBAT");
    await userEvent.type(screen.getByLabelText("Your name"), "Ada");
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.type(
      screen.getByLabelText("Password"),
      "correct horse battery",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create organisation" }),
    );
    expect(
      await screen.findByText(/sent a confirmation link to ada@example.com/),
    ).toBeInTheDocument();
  });

  it("rejects a short password before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<SignupPage />, { route: "/signup" });
    await userEvent.type(screen.getByLabelText("Password"), "short");
    await userEvent.click(
      screen.getByRole("button", { name: "Create organisation" }),
    );
    expect(
      await screen.findByText("Use at least 12 characters"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
