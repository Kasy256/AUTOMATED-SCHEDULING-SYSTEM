export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
