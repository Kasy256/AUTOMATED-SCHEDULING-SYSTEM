import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import "./index.css";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";
import { initSentry } from "@/lib/sentry";

import { App } from "./App";

initSentry();

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element in index.html");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // An API answer (403, 404, 422…) won't change on retry; a network blip might.
      retry: (count, error) => !isApiError(error) && count < 2,
      staleTime: 30_000,
    },
  },
});

// A data router (one splat route around <App>'s own <Routes>) so pages can use useBlocker.
const router = createBrowserRouter([
  {
    path: "*",
    element: (
      <AuthProvider>
        <App />
        <Toaster richColors closeButton />
      </AuthProvider>
    ),
  },
]);

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
