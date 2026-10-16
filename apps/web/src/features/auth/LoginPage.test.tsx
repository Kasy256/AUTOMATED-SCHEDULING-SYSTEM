import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { ApiError } from "@/lib/problem";
import { renderWithProviders } from "@/test/render";

import { LoginPage } from "./LoginPage";

function mockLogin(impl: () => Promise<void>) {
  const login = vi.fn(impl);
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedOut",
    me: null,
    login,
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    can: () => false,
  });
  return login;
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows one generic message for wrong credentials", async () => {
    mockLogin(() =>
      Promise.reject(
        new ApiError(401, "Unauthorized", "Invalid credentials", []),
      ),
    );
    renderWithProviders(<LoginPage />, { route: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect.",
    );
  });

  it("explains an unconfirmed email", async () => {
    mockLogin(() =>
      Promise.reject(
        new ApiError(403, "Forbidden", "Email address not confirmed", []),
      ),
    );
    renderWithProviders(<LoginPage />, { route: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
    await userEvent.type(screen.getByLabelText("Password"), "whatever-long");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Confirm your email address first",
    );
  });
});
