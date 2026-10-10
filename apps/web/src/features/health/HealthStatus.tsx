import { useHealth } from "@/api/generated/health/health";
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
  if (response.status !== 200) return <p>{response.data.title}</p>;

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
