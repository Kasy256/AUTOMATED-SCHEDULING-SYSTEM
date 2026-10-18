import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useListMembers } from "@/api/generated/members/members";
import type { ResourceResponse } from "@/api/generated/model";
import { updateResource } from "@/api/generated/resources/resources";
import { NativeSelect } from "@/components/NativeSelect";
import { Label } from "@/components/ui/label";
import { describeFailure } from "@/lib/conflict";

export function LinkedAccount({ resource }: { resource: ResourceResponse }) {
  const queryClient = useQueryClient();
  const { data: members = [] } = useListMembers();
  const active = members.filter((m) => m.status === "active");

  async function link(userId: string) {
    try {
      await updateResource(resource.id, { user_id: userId || null });
      await queryClient.invalidateQueries({
        predicate: (q) => String(q.queryKey[0]).includes("/resources"),
      });
      toast.success("Linked account saved");
    } catch (e) {
      toast.error(describeFailure(e, "This resource"));
    }
  }

  return (
    <div className="flex max-w-md flex-col gap-1.5">
      <Label htmlFor="linked-account">Linked account</Label>
      <NativeSelect
        id="linked-account"
        value={resource.user_id ?? ""}
        onChange={(e) => void link(e.target.value)}
      >
        <option value="">Not linked</option>
        {resource.user_id &&
          !active.some((m) => m.user_id === resource.user_id) && (
            <option value={resource.user_id}>Inactive account</option>
          )}
        {active.map((m) => (
          <option key={m.user_id} value={m.user_id}>
            {`${m.name} (${m.email})`}
          </option>
        ))}
      </NativeSelect>
      <p className="text-xs text-muted-foreground">
        The person signing in with this account sees this resource's timetable
        under My timetable.
      </p>
    </div>
  );
}
