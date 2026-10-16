import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { z } from "zod";

import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";

import { AuthLayout } from "./AuthLayout";

const schema = z.object({
  email: z.email("Enter an email address"),
  password: z.string().min(1, "Enter your password"),
});
type Values = z.infer<typeof schema>;

function loginMessage(error: unknown): string {
  if (!isApiError(error))
    return "Could not reach the server. Check your connection and try again.";
  if (error.status === 403)
    return "Confirm your email address first — check your inbox for the link.";
  if (error.status === 429)
    return "Too many attempts. Wait a minute and try again.";
  return "Email or password is incorrect.";
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema) });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async ({ email, password }) => {
    setMessage(null);
    try {
      await login(email, password);
      const next = params.get("next");
      // Only same-app paths: an open redirect would let a link send users elsewhere after login.
      void navigate(
        next?.startsWith("/") && !next.startsWith("//") ? next : "/",
        { replace: true },
      );
    } catch (error) {
      setMessage(loginMessage(error));
    }
  });

  return (
    <AuthLayout title="Sign in" subtitle="Welcome back.">
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
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...form.register("email")}
          />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            {...form.register("password")}
          />
          <FieldError message={errors.password?.message} />
        </div>
        <Button type="submit" disabled={isSubmitting}>
          Sign in
        </Button>
        <p className="text-sm text-muted-foreground">
          New here?{" "}
          <Link
            className="font-medium text-primary underline-offset-4 hover:underline"
            to="/signup"
          >
            Create an organisation
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
