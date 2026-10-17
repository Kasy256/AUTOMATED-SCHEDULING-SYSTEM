import { useParams } from "react-router";

import { PageHeader } from "@/components/PageHeader";
import { useAuth } from "@/lib/auth/AuthProvider";

import { DemandsSection } from "./DemandsSection";
import { SlotTemplatesSection } from "./SlotTemplatesSection";

export function DemandsPage() {
  const { scheduleId = "" } = useParams();
  const { can } = useAuth();
  const canEdit = can("config.manage");
  return (
    <>
      <PageHeader
        title="Demands & slots"
        description="What needs scheduling, and the times it can happen."
      />
      <div className="flex flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        <SlotTemplatesSection scheduleId={scheduleId} canEdit={canEdit} />
        <DemandsSection scheduleId={scheduleId} canEdit={canEdit} />
      </div>
    </>
  );
}
