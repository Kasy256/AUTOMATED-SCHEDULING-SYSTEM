import { useHealth } from "@/api/generated/health/health";
import type { Health503 } from "@/api/generated/model";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const yesNo = (value: boolean) => (value ? "yes" : "no");

function HealthBody() {
  const { data: response, isPending, isError } = useHealth();

  if (isPending) return <p>Checking API…</p>;
  if (isError) return <p>API unreachable</p>;
  if (response.status !== 200) {
    // Types only know the documented 503; proxies and crashes can return any status and body.
    const { title } = response.data as Partial<Health503>;
    return <p>{title ?? `API error (HTTP ${String(response.status)})`}</p>;
  }

  const { current_user, rolsuper, rolbypassrls } = response.data.database;
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
