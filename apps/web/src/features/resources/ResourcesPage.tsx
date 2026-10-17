import { useState } from "react";
import { Link } from "react-router";

import {
  useListResources,
  useListResourceTypes,
} from "@/api/generated/resources/resources";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth/AuthProvider";

import { filterResources } from "./filter";
import { ResourceDialog } from "./ResourceDialog";

export function ResourcesPage() {
  const { can } = useAuth();
  const { data: types = [] } = useListResourceTypes();
  const { data: resources = [], isPending } = useListResources();
  const [typeId, setTypeId] = useState("all");
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const typeName = new Map(types.map((t) => [t.id, t.name]));
  const shown = filterResources(resources, { typeId, query });

  return (
    <>
      <PageHeader
        title="Resources"
        description="People, spaces, assets and groups that can be scheduled."
        actions={
          can("config.manage") &&
          types.length > 0 && (
            <Button
              onClick={() => {
                setCreating(true);
              }}
            >
              New resource
            </Button>
          )
        }
      />
      <div className="flex flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs value={typeId} onValueChange={setTypeId}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              {types.map((t) => (
                <TabsTrigger key={t.id} value={t.id}>
                  {t.name}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Input
            aria-label="Search resources"
            placeholder="Search code, name or tag"
            className="max-w-xs"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
            }}
          />
        </div>
        {isPending ? (
          <TableSkeleton label="Loading resources" />
        ) : resources.length === 0 ? (
          <EmptyState
            illustration="import"
            title="No resources yet"
            description="Import a CSV from Imports, or add resources one by one."
          />
        ) : (
          <div className="rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="text-right">Capacity / size</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link
                        className="font-medium hover:underline"
                        to={`/resources/${r.id}`}
                      >
                        {r.name}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {r.code}
                    </TableCell>
                    <TableCell>
                      {typeName.get(r.resource_type_id) ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.tags.map((t) => (
                          <Badge key={t} variant="secondary">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.capacity ?? r.size ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
      {creating && (
        <ResourceDialog
          open={creating}
          onOpenChange={setCreating}
          types={types}
        />
      )}
    </>
  );
}
