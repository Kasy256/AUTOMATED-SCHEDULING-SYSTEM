import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";

export function renderWithProviders(
  ui: ReactElement,
  { route = "/", path = "*" }: { route?: string; path?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={createMemoryRouter(
            [
              { path, element: ui },
              ...(path === "*" ? [] : [{ path: "*", element: null }]),
            ],
            { initialEntries: [route] },
          )}
        />
      </QueryClientProvider>,
    ),
  };
}

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
