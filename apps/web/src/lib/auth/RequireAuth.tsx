import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { useAuth } from "./AuthProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading")
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );
  if (status === "signedOut") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}
