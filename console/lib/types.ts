// Shared types — mirror the Sentinel engine's JSON contract (see
// sentinel/src/sentinel/api/engine_api.py). The engine is the source of truth;
// the Console never invents these shapes.

export type Status = "ok" | "warn" | "root";
export type TimeRange = "10m" | "1h" | "24h";
export type Env = "prod" | "staging";

export interface ScenarioMeta {
  id: string;
  label: string;
  root: string;
  note: string;
}

export interface InvestigationStep {
  key: "detected" | "localized" | "correlated" | "proposed";
  title: string;
  detail: string;
  t?: number | null;
  metric?: string;
  service?: string;
  change?: string | null;
  gated?: boolean;
}

export interface Incident {
  detected: boolean;
  detectT?: number;
  incidentT?: number;
  mttd?: number;
  root?: string;
  localizationCorrect?: boolean;
  sloErrPct?: number;
  blastRadius?: { service: string; errorPct: number }[];
  evidence?: { p95Before: number; p95After: number; failingSpan: string | null };
  change?: { service: string; change: string; t: number } | null;
  steps?: InvestigationStep[];
  confidence?: number;
  method: string;
  failureModes: string[];
  report?: string;
  demo?: boolean;
}

export interface TopoService {
  id: string;
  status: Status;
  rps: number;
  errorPct: number;
  p95: number;
  dependsOn: string[];
}

export interface TopoEdge {
  source: string;
  target: string;
  erroring: boolean;
}

export interface Topology {
  detected: boolean;
  root: string | null;
  incidentT: number;
  services: TopoService[];
  edges: TopoEdge[];
  demo?: boolean;
}

export interface ChangeItem {
  service: string;
  change: string;
  t: number;
  score: number;
  serviceMatch: number;
  onsetProximity: number;
  recencyRank: number;
  isRoot: boolean;
}

export interface Changes {
  items: ChangeItem[];
  onsetT: number;
  root: string | null;
  demo?: boolean;
}

export interface Telemetry {
  service: string;
  range: TimeRange;
  t: string[];
  err: number[];
  p95: number[];
  rps: number[];
  slo: number;
  incident: [number, number] | null;
  changes: { t: number; label: string; service: string }[];
  demo?: boolean;
}

export interface HostGroup {
  service: string;
  total: number;
  healthy: number;
  warn: number;
  crit: number;
  cells: ("ok" | "warn" | "crit")[];
  status: Status;
}

export interface TraceSpan {
  name: string;
  service: string;
  depth: number;
  start: number;
  dur: number;
  status: "OK" | "ERROR";
}

export interface Panels {
  errorShare: { service: string; value: number; status: Status }[];
  spanThroughput: { service: string; rps: number; status: Status }[];
  hosts: HostGroup[];
  latencyHeatmap: {
    service: string;
    bands: string[];
    t: number[];
    cells: [number, number, number][];
    incidentT: number;
  };
  trace: { traceId: string; total: number; errorSpan: string; spans: TraceSpan[] };
  root: string | null;
  demo?: boolean;
}

export interface Frame {
  ts: number;
  root: string;
  services: Record<
    string,
    { err: number; p95: number; rps: number; status: Status }
  >;
  elevatedCount: number;
  demo?: boolean;
}

// The three-layer honesty story (GET /validation) — cards retrievable without
// running any training/validation pipeline.
export interface DetectorCard {
  name: string;
  dataset: string;
  model: string;
  source: string;
  metrics: {
    precision: number;
    recall: number;
    f1: number;
    roc_auc?: number;
    f1_point_adjusted?: number;
  };
  note?: string;
}
export interface LocalizationCard {
  rule: string;
  trained: boolean;
  note: string;
}
export interface ValidationCard {
  dataset: string;
  rule: string;
  source: string;
  incidents: number;
  recall_at_1: number;
  recall_at_3: number;
  detection_coverage: number;
  within_domain?: {
    recall_at_1: number;
    recall_at_3: number;
    detection_coverage: number;
    note?: string;
  };
  failure_modes: string[];
  boundary: string;
}
export interface ValidationLayer {
  id: "detection" | "localization" | "validation";
  title: string;
  kind: "learned" | "deterministic" | "empirical";
  subtitle: string;
  detectors?: DetectorCard[];
  card?: LocalizationCard | ValidationCard;
}
export interface Validation {
  principle: string;
  layers: ValidationLayer[];
}
