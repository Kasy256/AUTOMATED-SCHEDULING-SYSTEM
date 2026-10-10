import { HealthStatus } from "@/features/health/HealthStatus";

export function HomePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Cartlyf</h1>
      <HealthStatus />
    </main>
  );
}
