import { screen } from "@testing-library/react";

import * as auth from "@/lib/auth/AuthProvider";
import { jsonResponse, renderWithProviders } from "@/test/render";

import { ConfirmEmailPage } from "./ConfirmEmailPage";

describe("ConfirmEmailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses the session the confirmation returns and continues into the app", async () => {
    const adoptSession = vi.fn(() => Promise.resolve());
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedOut",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      adoptSession,
      can: () => false,
    });
    const token = {
      access_token: "t",
      token_type: "bearer",
      expires_in: 900,
      organisation_id: "o1",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(token))),
    );
    renderWithProviders(<ConfirmEmailPage />, {
      route: "/confirm-email?token=abc",
    });
    expect(
      await screen.findByRole("link", { name: "Continue" }),
    ).toHaveAttribute("href", "/");
    expect(adoptSession).toHaveBeenCalledWith(token);
  });
});
