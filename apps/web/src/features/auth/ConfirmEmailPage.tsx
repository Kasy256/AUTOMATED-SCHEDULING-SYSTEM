import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { confirmEmailRoute } from "@/api/generated/auth/auth";
import { Button } from "@/components/ui/button";

import { AuthLayout } from "./AuthLayout";

export function ConfirmEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "done" | "failed">(
    token ? "working" : "failed",
  );
  const sent = useRef(false);

  useEffect(() => {
    // StrictMode runs effects twice in development; the link must be used once.
    if (!token || sent.current) return;
    sent.current = true;
    confirmEmailRoute({ token }).then(
      () => {
        setState("done");
      },
      () => {
        setState("failed");
      },
    );
  }, [token]);

  if (state === "working") return <AuthLayout title="Confirming…" />;
  if (state === "failed")
    return (
      <AuthLayout
        title="This link doesn't work"
        subtitle="It may have expired or already been used."
      >
        <Button asChild>
          <Link to="/login">Go to sign in</Link>
        </Button>
      </AuthLayout>
    );
  return (
    <AuthLayout title="Email confirmed" subtitle="Your organisation is ready.">
      <Button asChild>
        <Link to="/login">Sign in</Link>
      </Button>
    </AuthLayout>
  );
}
