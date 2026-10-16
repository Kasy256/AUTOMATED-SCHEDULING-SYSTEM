import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  deleteResourceType,
  getListResourceTypesQueryKey,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import type { ResourceTypeResponse } from "@/api/generated/model";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/lib/auth/AuthProvider";
import { describeFailure } from "@/lib/conflict";

import { ResourceTypeDialog } from "./ResourceTypeDialog";

export function ResourceTypesPage() {
  const { can } = useAuth();
  const manage = can("config.manage");
  const queryClient = useQueryClient();
  const { data: types = [], isPending } = useListResourceTypes();
  const [editing, setEditing] = useState<ResourceTypeResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<ResourceTypeResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await deleteResourceType(deleting.id);
      toast.success(`${deleting.name} deleted`);
      await queryClient.invalidateQueries({
        queryKey: getListResourceTypesQueryKey(),
      });
    } catch (error) {
      setFailure(describeFailure(error, deleting.name));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Resource types"
        description="The kinds of things you schedule, and the attributes each one carries."
        actions={
          manage && (
            <Button
              onClick={() => {
                setEditing(null);
                setDialogOpen(true);
              }}
            >
              New resource type
            </Button>
          )
        }
      />
      <div className="flex flex-col gap-4 p-6">
        {failure && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{failure}</AlertDescription>
          </Alert>
        )}
        {!isPending && types.length === 0 ? (
          <EmptyState
            title="No resource types yet"
            description="Pick an industry template in the setup wizard, or create types such as Lecturer, Room or Nurse."
          />
        ) : (
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Attributes</TableHead>
                  {manage && (
                    <TableHead className="w-24">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {types.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell className="font-mono text-xs">{t.key}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{t.kind}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {(t.attribute_schema.attributes ?? [])
                        .map((a) => a.label ?? a.key)
                        .join(", ") || "—"}
                    </TableCell>
                    {manage && (
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${t.name}`}
                          onClick={() => {
                            setEditing(t);
                            setDialogOpen(true);
                          }}
                        >
                          <Pencil className="size-4" aria-hidden />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${t.name}`}
                          onClick={() => {
                            setFailure(null);
                            setDeleting(t);
                          }}
                        >
                          <Trash2 className="size-4" aria-hidden />
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
      {dialogOpen && (
        <ResourceTypeDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          editing={editing}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title={`Delete ${deleting?.name ?? ""}?`}
        description="This cannot be undone. Types still used by resources or rules cannot be deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
