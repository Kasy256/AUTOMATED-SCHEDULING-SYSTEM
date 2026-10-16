import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router";

import {
  loginRoute,
  logoutRoute,
  me as fetchMe,
  switchOrganisation as switchOrganisationRequest,
} from "@/api/generated/auth/auth";
import type { MeResponse } from "@/api/generated/model";
import { onSignedOut } from "@/api/client";
import { can as canWith, type Action } from "@/lib/permissions";

import {
  getTokenOrganisation,
  refreshAccessToken,
  setAccessToken,
  setSession,
  subscribeToken,
  withSessionLock,
} from "./session";

interface AuthState {
  status: "loading" | "signedOut" | "signedIn";
  me: MeResponse | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  switchOrganisation: (organisationId: string) => Promise<void>;
  can: (action: Action) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const meRef = useRef<MeResponse | null>(null);

  const signedOut = useCallback(() => {
    setAccessToken(null);
    meRef.current = null;
    setMe(null);
    setStatus("signedOut");
    queryClient.clear();
  }, [queryClient]);

  const loadMe = useCallback(async () => {
    const next = await fetchMe();
    meRef.current = next;
    setMe(next);
    setStatus("signedIn");
  }, []);

  useEffect(() => {
    const restore = async () => {
      if (await refreshAccessToken()) await loadMe();
      else signedOut();
    };
    restore().catch(signedOut);
    return onSignedOut(signedOut);
  }, [loadMe, signedOut]);

  // The active organisation lives with the shared refresh cookie: a switch in this tab, a switch or
  // accepted invitation in another tab, or a new login can all hand this tab a token for a different
  // organisation. Nothing from the previous organisation may stay on screen or receive writes.
  useEffect(
    () =>
      subscribeToken(() => {
        const org = getTokenOrganisation();
        const current = meRef.current;
        if (!current || org === null || org === current.organisation_id) return;
        queryClient.clear();
        void loadMe().then(() => navigate("/", { replace: true }), signedOut);
      }),
    [loadMe, navigate, queryClient, signedOut],
  );

  const value = useMemo<AuthState>(
    () => ({
      status,
      me,
      async login(email, password) {
        // A previous user's cached data must never render under the new identity.
        queryClient.clear();
        const token = await loginRoute({ email, password });
        meRef.current = null;
        setSession(token);
        await loadMe();
      },
      async logout() {
        await logoutRoute().catch(() => undefined);
        signedOut();
      },
      async switchOrganisation(organisationId) {
        const token = await withSessionLock(() =>
          switchOrganisationRequest({ organisation_id: organisationId }),
        );
        setSession(token);
      },
      can: (action) => (me ? canWith(me.roles, action) : false),
    }),
    [status, me, loadMe, signedOut, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- the hook belongs with its provider
export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside <AuthProvider>");
  return auth;
}
