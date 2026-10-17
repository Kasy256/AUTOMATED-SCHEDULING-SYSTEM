import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router";
import { z } from "zod";

import { acceptInvitationRoute } from "@/api/generated/auth/auth";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyApiError } from "@/lib/forms";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";

import { AuthLayout } from "./AuthLayout";

const schema = z.object({
  password: z.string().min(12, "Use at least 12 characters").max(256),
});
type Values = z.infer<typeof schema>;

export function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [accepted, setAccepted] = useState(false);
  const { adoptSession } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema) });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async ({ password }) => {
    if (!token) return;
    setMessage(null);
    try {
      // Accepting signs the person in to the organisation they just joined.
      await adoptSession(await acceptInvitationRoute({ token, password }));
      setAccepted(true);
    } catch (error) {
      if (isApiError(error) && error.status === 401) {
        setMessage("That password doesn't match your existing account.");
      } else if (isApiError(error) && error.status === 400) {
        setMessage("This invitation link is invalid or has expired.");
      } else {
        setMessage(applyApiError(error, form.setError, ["password"]));
      }
    }
  });

  if (!token)
    return (
      <AuthLayout
        title="This link doesn't work"
        subtitle="It is missing its invitation token."
      >
        <Button asChild>
          <Link to="/login">Go to sign in</Link>
        </Button>
      </AuthLayout>
    );

  if (accepted)
    return (
      <AuthLayout
        title="You're in"
        subtitle="Your invitation has been accepted."
      >
        <Button asChild>
          <Link to="/">Continue</Link>
        </Button>
      </AuthLayout>
    );

  return (
    <AuthLayout title="Accept your invitation">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => void onSubmit(e)}
        noValidate
      >
        {message && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            aria-describedby="password-hint"
            {...form.register("password")}
          />
          <p id="password-hint" className="text-xs text-muted-foreground">
            New to Cartlyf? Choose a password. Already have an account? Enter
            its password.
          </p>
          <FieldError message={errors.password?.message} />
        </div>
        <Button type="submit" disabled={isSubmitting}>
          Accept invitation
        </Button>
      </form>
    </AuthLayout>
  );
}
