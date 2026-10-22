export type Role = "admin" | "assessor" | "viewer";
export type EntityType = "lob" | "program" | "app";
export type Horizon = "now" | "next" | "later";
export type Confidence = "low" | "med" | "high";
export type Status = "gap" | "partial" | "val" | "strong";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Engagement {
  id: number;
  client: string;
  title: string;
  start_date: string;
  weeks: number;
  interviews_planned: number;
  archived: boolean;
  created_at: string;
  entities?: number;
  interviews?: number;
  evidence?: number;
  snapshots?: number;
}

export interface ScaleLevel {
  label: string;
  description: string;
}

export interface FrameworkSettings {
  scale: ScaleLevel[];
  thresholds: { gap: number; strong: number };
  weighting: "apps" | "equal";
}

export interface FocusArea {
  id: number;
  key: string;
  name: string;
  description: string;
  question: string;
  recommendation: string;
  horizon: Horizon;
  position: number;
  pillar_id: number;
}

export interface Pillar {
  id: number;
  key: string;
  name: string;
  short: string;
  target: number;
  weight: number;
  color: number;
  position: number;
  focus_areas: FocusArea[];
}

export interface Entity {
  id: number;
  name: string;
  type: EntityType;
  parent_id: number | null;
  apps: number;
  art: string;
  owner: string;
  criticality: "High" | "Medium" | "Low";
  position: number;
  created_at: string;
}

export interface Assessment {
  entity_id: number;
  focus_area_id: number;
  score: number | null;
  confidence: Confidence | null;
  notes: string;
  updated_by: number | null;
  updated_at: string;
}

export interface Cell {
  score: number | null;
  inherited: boolean;
  confidence: Confidence | null;
  interviews: number;
  evidence: number;
  status: Status;
}

export interface EntityAnalytics {
  depth: number;
  path: string;
  overall: number | null;
  pillars: (number | null)[];
  coverage: number;
  cells: Record<string, Cell>;
}

export interface Analytics {
  order: number[];
  top_level: number[];
  entities: Record<string, EntityAnalytics>;
  enterprise: {
    overall: number | null;
    level: string;
    coverage: number;
    pillars: (number | null)[];
    cells: Record<string, number | null>;
    counts: Record<Status, number>;
    total: number;
  };
  ranked: { focus_area_id: number; score: number }[];
  conflicts: { entity_id: number; a: number; b: number; a_score: number; b_score: number; message: string }[];
  evidence_gaps: { entity_id: number; focus_area_id: number; why: string }[];
}

export interface Workspace {
  engagement: Engagement;
  settings: FrameworkSettings;
  pillars: Pillar[];
  entities: Entity[];
  assessments: Assessment[];
  analytics: Analytics;
}

export interface Finding {
  focus_area_id: number;
  score: number | null;
  confidence: Confidence;
  finding: string;
  followup: string;
  applied: boolean;
}

export interface Interview {
  id: number;
  entity_id: number | null;
  date: string;
  stakeholder: string;
  type: string;
  status: "scheduled" | "completed";
  notes: string;
  findings: Finding[] | null;
  applied: number;
  focus_area_ids: number[];
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  id: number;
  entity_id: number | null;
  name: string;
  kind: "file" | "link";
  doc_type: string;
  summary: string;
  signals: string[];
  url: string;
  has_file: boolean;
  content_type: string;
  size: number;
  classified_by: string;
  focus_area_ids: number[];
  created_by: number | null;
  created_at: string;
}

export interface ActivityItem {
  id: number;
  kind: string;
  text: string;
  user_id: number | null;
  created_at: string;
}

export interface SnapshotData {
  overall: number | null;
  level: string;
  coverage: number;
  apps: number;
  counts: Record<Status, number>;
  total: number;
  interviews: number;
  evidence: number;
  evidence_gaps: number;
  conflicts: number;
  pillars: { name: string; short: string; color: number; target: number; score: number | null }[];
  entities: { name: string; type: EntityType; apps: number; overall: number | null; pillars: (number | null)[] }[];
  gaps: { name: string; pillar: string; score: number; rec: string; status?: Status }[];
  strengths: { name: string; score: number; best: string }[];
  roadmap: Record<Horizon, { name: string; rec: string; score: number; target: number }[]>;
  scale: string[];
}

export interface SnapshotMeta {
  id: number;
  version: number;
  note: string;
  created_by: number | null;
  created_at: string;
  overall: number | null;
}

export interface Snapshot extends SnapshotMeta {
  narrative: string;
  data: SnapshotData;
}
