import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as auth from "@/lib/auth/AuthProvider";
import { ApiError } from "@/lib/problem";
import { renderWithProviders } from "@/test/render";
import { Route, Routes } from "react-router";

import { LoginPage } from "./LoginPage";

function mockLogin(impl: () => Promise<void>) {
  const login = vi.fn(impl);
  vi.spyOn(auth, "useAuth").mockReturnValue({
    status: "signedOut",
    me: null,
    login,
    logout: vi.fn(),
    switchOrganisation: vi.fn(),
    adoptSession: vi.fn(),
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
  it("sends an already signed-in visitor home", async () => {
    vi.spyOn(auth, "useAuth").mockReturnValue({
      status: "signedIn",
      me: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganisation: vi.fn(),
      adoptSession: vi.fn(),
      can: () => true,
    });
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>home page</p>} />
      </Routes>,
      { route: "/login" },
    );
    expect(await screen.findByText("home page")).toBeInTheDocument();
  });
});
