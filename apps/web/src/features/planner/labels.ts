export const versionLabel = (v: { number: number; status: string }) =>
  `Version ${String(v.number)} · ${v.status}`;
