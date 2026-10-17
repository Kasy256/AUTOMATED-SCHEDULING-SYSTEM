import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  createInvitation,
  getListMembersQueryKey,
  setMemberRoles,
  useListMembers,
} from "@/api/generated/members/members";
import type { MemberResponse, Role } from "@/api/generated/model";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { FieldError } from "@/components/FieldError";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isApiError } from "@/lib/problem";

import { RoleChecklist } from "./RoleChecklist";
import { ROLE_LABELS } from "./roles";

const STATUS: Record<string, string> = { active: "Active", invited: "Invited" };

function failureText(error: unknown): string {
  if (!isApiError(error))
    return "Could not reach the server. Check your connection and try again.";
  if (error.status === 409 && /admin/i.test(error.detail ?? ""))
    return "An organisation needs at least one admin.";
  return error.detail ?? error.title;
}

function InviteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send() {
    setError(null);
    if (!email.includes("@") || !name.trim()) {
      setError("Enter an email address and a name");
      return;
    }
    if (roles.length === 0) {
      setError("Choose at least one role");
      return;
    }
    setBusy(true);
    try {
      await createInvitation({ email: email.trim(), name: name.trim(), roles });
      await queryClient.invalidateQueries({
        queryKey: getListMembersQueryKey(),
      });
      toast.success(`Invitation sent to ${email.trim()}`);
      onOpenChange(false);
    } catch (e) {
      setError(failureText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite member</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="inv-email">Email</Label>
            <Input
              id="inv-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="inv-name">Name</Label>
            <Input
              id="inv-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <RoleChecklist
            idPrefix="inv-role"
            value={roles}
            onChange={setRoles}
          />
          <FieldError message={error ?? undefined} />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              Send invitation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RolesDialog({
  member,
  onOpenChange,
}: {
  member: MemberResponse;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [roles, setRoles] = useState<Role[]>(member.roles);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setError(null);
    if (roles.length === 0) {
      setError("Choose at least one role");
      return;
    }
    setBusy(true);
    try {
      await setMemberRoles(member.membership_id, { roles });
      await queryClient.invalidateQueries({
        queryKey: getListMembersQueryKey(),
      });
      toast.success(`Roles updated for ${member.name}`);
      onOpenChange(false);
    } catch (e) {
      setError(failureText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{`Roles for ${member.name}`}</DialogTitle>
        </DialogHeader>
        <RoleChecklist idPrefix="edit-role" value={roles} onChange={setRoles} />
        {error && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={busy} onClick={() => void save()}>
            Save roles
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function MembersPage() {
  const { can } = useAuth();
  const { data: members = [], isPending } = useListMembers();
  const [inviting, setInviting] = useState(false);
  const [editing, setEditing] = useState<MemberResponse | null>(null);
  const manage = can("members.manage");

  return (
    <>
      <PageHeader
        title="Members"
        description="Who can use this organisation, and what each person may do."
        actions={
          manage && (
            <Button onClick={() => setInviting(true)}>Invite member</Button>
          )
        }
      />
      <div className="px-4 py-6 sm:px-6 lg:px-8">
        {isPending ? (
          <TableSkeleton label="Loading members" />
        ) : members.length === 0 ? (
          <EmptyState
            illustration="team"
            title="No members yet"
            description="Invite planners, viewers and the people you schedule."
          />
        ) : (
          <div className="rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead>Status</TableHead>
                  {manage && (
                    <TableHead className="w-28">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.membership_id}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell>{m.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {m.roles.map((r) => (
                          <Badge key={r} variant="secondary">
                            {ROLE_LABELS[r]}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>{STATUS[m.status] ?? m.status}</TableCell>
                    {manage && (
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Edit roles of ${m.name}`}
                          onClick={() => setEditing(m)}
                        >
                          Edit roles
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
      {inviting && <InviteDialog open={inviting} onOpenChange={setInviting} />}
      {editing && (
        <RolesDialog
          member={editing}
          onOpenChange={(open) => {
            if (!open) setEditing(null);
          }}
        />
      )}
    </>
  );
}
