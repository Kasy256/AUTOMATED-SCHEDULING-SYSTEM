export function FieldError({
  id,
  message,
}: {
  id?: string;
  message?: string | undefined;
}) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="text-xs text-destructive">
      {message}
    </p>
  );
}
