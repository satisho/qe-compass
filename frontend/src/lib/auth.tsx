import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { api } from "../api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
  canWrite: boolean;
  isAdmin: boolean;
  refresh: () => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState>({
  user: null, loading: true, canWrite: false, isAdmin: false, refresh: () => undefined, signOut: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get<{ user: User | null }>("/api/auth/session")).user,
    staleTime: 5 * 60_000,
    retry: false,
  });
  useEffect(() => {
    const onUnauthorized = () => qc.setQueryData(["me"], null);
    window.addEventListener("qec:unauthorized", onUnauthorized);
    return () => window.removeEventListener("qec:unauthorized", onUnauthorized);
  }, [qc]);
  const user = q.data ?? null;
  const value: AuthState = {
    user,
    loading: q.isLoading,
    canWrite: user?.role === "admin" || user?.role === "assessor",
    isAdmin: user?.role === "admin",
    refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
    signOut: async () => {
      await api.post("/api/auth/logout").catch(() => undefined);
      qc.setQueryData(["me"], null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
