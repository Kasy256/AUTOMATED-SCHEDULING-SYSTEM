import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  loginRoute,
  logoutRoute,
  me as fetchMe,
  switchOrganisation as switchOrganisationRequest,
} from "@/api/generated/auth/auth";
import type { MeResponse } from "@/api/generated/model";
import { onSignedOut } from "@/api/client";
import { can as canWith, type Action } from "@/lib/permissions";

import { refreshAccessToken, setAccessToken } from "./session";

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
  const [me, setMe] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const signedOut = useCallback(() => {
    setAccessToken(null);
    setMe(null);
    setStatus("signedOut");
    queryClient.clear();
  }, [queryClient]);

  const loadMe = useCallback(async () => {
    setMe(await fetchMe());
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

  const value = useMemo<AuthState>(
    () => ({
      status,
      me,
      async login(email, password) {
        const token = await loginRoute({ email, password });
        setAccessToken(token.access_token);
        await loadMe();
      },
      async logout() {
        await logoutRoute().catch(() => undefined);
        signedOut();
      },
      async switchOrganisation(organisationId) {
        const token = await switchOrganisationRequest({
          organisation_id: organisationId,
        });
        setAccessToken(token.access_token);
        // Nothing cached for the previous organisation may render after the switch.
        queryClient.clear();
        await loadMe();
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
