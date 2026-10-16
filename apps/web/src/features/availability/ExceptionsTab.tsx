export function ExceptionsTab(props: { resourceId: string; canEdit: boolean }) {
  return (
    <p
      className="py-6 text-sm text-muted-foreground"
      data-resource={props.resourceId}
    >
      Loading…
    </p>
  );
}
