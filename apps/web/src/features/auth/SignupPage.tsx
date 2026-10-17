import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { signup } from "@/api/generated/auth/auth";
import { FieldError } from "@/components/FieldError";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyApiError } from "@/lib/forms";
import { browserTimezone } from "@/lib/time";

import { AuthLayout } from "./AuthLayout";

const schema = z.object({
  organisation_name: z
    .string()
    .trim()
    .min(1, "Enter your organisation's name")
    .max(200),
  timezone: z.string().min(1, "Choose a timezone"),
  name: z.string().trim().min(1, "Enter your name").max(200),
  email: z.email("Enter an email address"),
  password: z.string().min(12, "Use at least 12 characters").max(256),
});
type Values = z.infer<typeof schema>;
const FIELDS = [
  "organisation_name",
  "timezone",
  "name",
  "email",
  "password",
] as const;
const LABELS: Record<(typeof FIELDS)[number], string> = {
  organisation_name: "Organisation name",
  timezone: "Timezone",
  name: "Your name",
  email: "Email",
  password: "Password",
};

export function SignupPage() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { timezone: browserTimezone() },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    try {
      await signup(values);
      setSentTo(values.email);
    } catch (error) {
      setMessage(applyApiError(error, form.setError, FIELDS));
    }
  });

  if (sentTo) {
    return (
      <AuthLayout
        title="Check your email"
        subtitle={`We sent a confirmation link to ${sentTo}.`}
      >
        <p className="text-sm text-muted-foreground">
          Open the link to finish creating your organisation. It expires in 24
          hours.
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Create your organisation"
      subtitle="Set up your scheduling workspace in a few minutes."
    >
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
        {FIELDS.map((field) => (
          <div key={field} className="flex flex-col gap-1.5">
            <Label htmlFor={field}>{LABELS[field]}</Label>
            <Input
              id={field}
              type={
                field === "password"
                  ? "password"
                  : field === "email"
                    ? "email"
                    : "text"
              }
              autoComplete={
                field === "password"
                  ? "new-password"
                  : field === "email"
                    ? "email"
                    : undefined
              }
              list={field === "timezone" ? "timezones" : undefined}
              aria-invalid={!!errors[field]}
              {...form.register(field)}
            />
            <FieldError message={errors[field]?.message} />
          </div>
        ))}
        <datalist id="timezones">
          {Intl.supportedValuesOf("timeZone").map((tz) => (
            <option key={tz} value={tz} />
          ))}
        </datalist>
        <Button type="submit" disabled={isSubmitting}>
          Create organisation
        </Button>
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            className="font-medium text-primary hover:underline"
            to="/login"
          >
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
