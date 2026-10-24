import { execFileSync } from "node:child_process";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "../../../..");

function latestBody(email: string, subjectLike: string): string {
  const safe = email.replace(/'/g, "''");
  const sql = `select body from email_outbox where to_address = '${safe}' and subject like '${subjectLike}' order by created_at desc limit 1`;
  // Test-only: the compose superuser reads the outbox the app writes; the app itself never does.
  return execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "postgres",
      "-d",
      "cartlyf",
      "-At",
      "-c",
      sql,
    ],
    { cwd: repoRoot, encoding: "utf8" },
  ).trim();
}

async function linkFrom(
  email: string,
  subjectLike: string,
  route: string,
): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const match = new RegExp(`/${route}\\?token=[^\\s]+`).exec(
      latestBody(email, subjectLike),
    );
    if (match) return match[0];
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`No ${route} email for ${email}`);
}

export const confirmationLink = (email: string) =>
  linkFrom(email, "Confirm your email%", "confirm-email");
export const invitationLink = (email: string) =>
  linkFrom(email, "You have been invited%", "accept-invitation");
