import { useParams } from "react-router";

import {
  useGetResource,
  useGetResourceType,
} from "@/api/generated/resources/resources";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AvailabilityTab } from "@/features/availability/AvailabilityTab";
import { ExceptionsTab } from "@/features/availability/ExceptionsTab";
import { useAuth } from "@/lib/auth/AuthProvider";

import { AttributeForm } from "./AttributeForm";

export function ResourceDetailPage() {
  const { resourceId = "" } = useParams();
  const { can } = useAuth();
  const { data: resource, error } = useGetResource(resourceId);
  const { data: type } = useGetResourceType(resource?.resource_type_id ?? "", {
    query: { enabled: resource !== undefined },
  });
  if (error)
    return (
      <PageHeader
        title="Resource not found"
        description="It may have been deleted."
      />
    );
  if (!resource || !type)
    return (
      <div role="status" className="p-8 text-muted-foreground">
        Loading…
      </div>
    );
  const canEdit = can("config.manage");
  return (
    <>
      <PageHeader
        title={resource.name}
        description={`${type.name} · ${resource.code}`}
        actions={
          <div className="flex flex-wrap gap-1">
            {resource.tags.map((t) => (
              <Badge key={t} variant="secondary">
                {t}
              </Badge>
            ))}
          </div>
        }
      />
      <Tabs defaultValue="details" className="px-4 py-6 sm:px-6 lg:px-8">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="availability">Weekly availability</TabsTrigger>
          <TabsTrigger value="exceptions">Exceptions</TabsTrigger>
        </TabsList>
        <TabsContent value="details">
          <AttributeForm
            defs={type.attribute_schema.attributes ?? []}
            kind={type.kind}
            resource={resource}
            canEdit={canEdit}
          />
        </TabsContent>
        <TabsContent value="availability">
          <AvailabilityTab resourceId={resource.id} canEdit={canEdit} />
        </TabsContent>
        <TabsContent value="exceptions">
          <ExceptionsTab resourceId={resource.id} canEdit={canEdit} />
        </TabsContent>
      </Tabs>
    </>
  );
}
