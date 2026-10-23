import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Me } from "../types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  /** Two-step verification is required here and this user hasn't set it up yet. */
  needsMfaSetup: boolean;
  /** Why the last session ended, e.g. after inactivity. */
  endedReason: string;
  canWrite: boolean;
  isAdmin: boolean;
  refresh: () => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState>({
  user: null, loading: true, needsMfaSetup: false, endedReason: "", canWrite: false, isAdmin: false, refresh: () => undefined, signOut: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [endedReason, setEndedReason] = useState("");
  const q = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const r = await api.get<{ user: Me | null; require_mfa: boolean; idle_minutes: number }>("/api/auth/session");
      return r.user ? { ...r.user, require_mfa: r.require_mfa, idle_minutes: r.idle_minutes } : null;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
  useEffect(() => {
    const onUnauthorized = (e: Event) => {
      if (qc.getQueryData(["me"])) setEndedReason((e as CustomEvent<string>).detail || "");
      qc.setQueryData(["me"], null);
    };
    window.addEventListener("qec:unauthorized", onUnauthorized);
    return () => window.removeEventListener("qec:unauthorized", onUnauthorized);
  }, [qc]);
  const user = q.data ?? null;
  const value: AuthState = {
    user,
    loading: q.isLoading,
    needsMfaSetup: !!user && !!user.require_mfa && !user.mfa_enabled,
    endedReason,
    canWrite: user?.role === "admin" || user?.role === "assessor",
    isAdmin: user?.role === "admin",
    refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
    signOut: async () => {
      await api.post("/api/auth/logout").catch(() => undefined);
      setEndedReason("");
      qc.setQueryData(["me"], null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
