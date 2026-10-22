import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type {
  ActivityItem, Entity, Evidence, FocusArea, Interview, Pillar, SnapshotMeta, Workspace,
} from "../types";
import { useToast } from "./toast";

export const useEid = () => Number(useParams().eid);
export const base = (eid: number) => `/api/engagements/${eid}`;

export function useWorkspace(eid: number) {
  return useQuery({ queryKey: ["ws", eid], queryFn: () => api.get<Workspace>(`${base(eid)}/workspace`), enabled: !!eid });
}
export function useInterviews(eid: number) {
  return useQuery({ queryKey: ["interviews", eid], queryFn: () => api.get<Interview[]>(`${base(eid)}/interviews`) });
}
export function useEvidence(eid: number) {
  return useQuery({ queryKey: ["evidence", eid], queryFn: () => api.get<Evidence[]>(`${base(eid)}/evidence`) });
}
export function useActivity(eid: number) {
  return useQuery({ queryKey: ["activity", eid], queryFn: () => api.get<ActivityItem[]>(`${base(eid)}/activity?limit=30`) });
}
export function useSnapshots(eid: number) {
  return useQuery({ queryKey: ["snapshots", eid], queryFn: () => api.get<SnapshotMeta[]>(`${base(eid)}/snapshots`) });
}
export function useDirectory() {
  const q = useQuery({ queryKey: ["directory"], queryFn: () => api.get<{ id: number; name: string }[]>("/api/users/directory"), staleTime: 60_000 });
  return useMemo(() => new Map((q.data || []).map((u) => [u.id, u.name])), [q.data]);
}

/** Mutation that refreshes the workspace-derived queries and reports errors as toasts. */
export function useMut<TVars, TRes = unknown>(
  eid: number,
  fn: (v: TVars) => Promise<TRes>,
  opts: { also?: string[]; success?: string | ((r: TRes, v: TVars) => string | undefined); onSuccess?: (r: TRes, v: TVars) => void } = {},
) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r, v) => {
      for (const k of ["ws", "activity", ...(opts.also || [])]) qc.invalidateQueries({ queryKey: [k, eid] });
      const msg = typeof opts.success === "function" ? opts.success(r, v) : opts.success;
      if (msg) toast(msg);
      opts.onSuccess?.(r, v);
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
}

/** Derived lookups over a loaded workspace. */
export function useModel(ws: Workspace | undefined) {
  return useMemo(() => {
    const pillars: Pillar[] = ws?.pillars || [];
    const fas: (FocusArea & { pi: number })[] = pillars.flatMap((p, pi) => p.focus_areas.map((f) => ({ ...f, pi })));
    const faById = new Map(fas.map((f) => [f.id, f]));
    const entities = ws?.entities || [];
    const entById = new Map(entities.map((e) => [e.id, e]));
    const order = ws?.analytics.order || entities.map((e) => e.id);
    const tree = order
      .map((id) => ({ e: entById.get(id)!, depth: ws?.analytics.entities[id]?.depth ?? 0 }))
      .filter((x) => x.e);
    const children = (id: number) => entities.filter((e) => e.parent_id === id);
    const descendants = (id: number): number[] => {
      const out: number[] = [];
      const stack = [id];
      while (stack.length) {
        for (const c of children(stack.pop()!)) {
          if (!out.includes(c.id)) {
            out.push(c.id);
            stack.push(c.id);
          }
        }
      }
      return out;
    };
    const path = (id: number | null) => (id != null ? ws?.analytics.entities[id]?.path || entById.get(id)?.name || "" : "");
    const assessment = (eid: number, fid: number) => ws?.assessments.find((a) => a.entity_id === eid && a.focus_area_id === fid);
    const cell = (eid: number, fid: number) => ws?.analytics.entities[eid]?.cells[fid];
    const level = (n: number | null | undefined) =>
      n == null ? "Not assessed" : ws?.settings.scale[Math.max(1, Math.min(5, Math.round(n))) - 1]?.label || `Level ${n}`;
    const inScope = (sel: number | "all", id: number | null) =>
      sel === "all" || id === sel || (id != null && descendants(sel).includes(id));
    const topLevel: Entity[] = (ws?.analytics.top_level || []).map((id) => entById.get(id)!).filter(Boolean);
    return { pillars, fas, faById, entities, entById, tree, children, descendants, path, assessment, cell, level, inScope, topLevel };
  }, [ws]);
}

export type Model = ReturnType<typeof useModel>;
