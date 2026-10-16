import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "@/components/AppShell";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ConfirmEmailPage } from "@/features/auth/ConfirmEmailPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { DemandsPage } from "@/features/demands/DemandsPage";
import { ImportsPage } from "@/features/imports/ImportsPage";
import { MembersPage } from "@/features/members/MembersPage";
import { ResourceTypesPage } from "@/features/resource-types/ResourceTypesPage";
import { ResourceDetailPage } from "@/features/resources/ResourceDetailPage";
import { ResourcesPage } from "@/features/resources/ResourcesPage";
import { RulesPage } from "@/features/rules/RulesPage";
import { OverviewPage } from "@/features/schedules/OverviewPage";
import { SetupWizard } from "@/features/setup/SetupWizard";
import { HomeRedirect } from "@/features/schedules/HomeRedirect";
import { RequireAuth } from "@/lib/auth/RequireAuth";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/confirm-email" element={<ConfirmEmailPage />} />
      <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
      <Route
        path="/setup"
        element={
          <RequireAuth>
            <SetupWizard />
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<HomeRedirect />} />
        <Route path="schedules/:scheduleId">
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="demands" element={<DemandsPage />} />
          <Route path="rules" element={<RulesPage />} />
        </Route>
        <Route path="resources" element={<ResourcesPage />} />
        <Route path="resources/:resourceId" element={<ResourceDetailPage />} />
        <Route path="resource-types" element={<ResourceTypesPage />} />
        <Route path="imports" element={<ImportsPage />} />
        <Route path="members" element={<MembersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
