import { useHealth } from "@/api/generated/health/health";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GENERIC_TITLE, isApiError } from "@/lib/problem";

const yesNo = (value: boolean) => (value ? "yes" : "no");

function errorText(error: Error): string {
  if (!isApiError(error)) return "API unreachable";
  // Proxies and crashes can answer without a problem body; the status is all there is.
  return error.title === GENERIC_TITLE
    ? `API error (HTTP ${String(error.status)})`
    : error.title;
}

function HealthBody() {
  const { data, isPending, error } = useHealth();

  if (isPending) return <p>Checking API…</p>;
  if (error) return <p>{errorText(error)}</p>;

  const { current_user, rolsuper, rolbypassrls } = data.database;
  return (
    <div className="flex flex-col gap-1">
      <p>API ok — connected as {current_user}</p>
      <p className="text-muted-foreground">
        superuser: {yesNo(rolsuper)} · BYPASSRLS: {yesNo(rolbypassrls)}
      </p>
    </div>
  );
}

export function HealthStatus() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>System health</CardTitle>
        <CardDescription>API and database connection</CardDescription>
      </CardHeader>
      <CardContent>
        <HealthBody />
      </CardContent>
    </Card>
  );
}
