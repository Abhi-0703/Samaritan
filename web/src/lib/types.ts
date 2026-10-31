// Shared types. Mirror api/app/schemas.py and plan.md Section 10.2 exactly (snake_case).

export type Severity = "critical" | "high" | "medium";
export type CallStatus = "queued" | "transcribing" | "analysing" | "done" | "failed";
export type Language = "hinglish" | "marathi";
export type ReviewerStatus = "open" | "confirmed" | "dismissed";
export type DetectedBy = "rules" | "llm" | "both" | "metadata";

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface Agent {
  id: string;
  name: string;
  team: string;
  calls_count: number;
  avg_score: number | null;
  critical_count: number;
  violation_rate: number; // 0..1
  top_rule_code: string | null;
}

export interface Call {
  id: string;
  test_key: string | null;
  agent_id: string;
  agent_name: string;
  loan_ref: string;
  called_at: string;
  duration_s: number | null;
  language: Language;
  status: CallStatus;
  score: number | null;
  violations_count: number;
  max_severity: Severity | null;
  error: string | null;
  borrower_requested_time: boolean;
}

export interface Segment {
  id: string;
  index: number;
  speaker: "agent" | "borrower" | "unknown";
  start_s: number;
  end_s: number;
  text: string; // masked
}

export interface Violation {
  id: string;
  call_id: string;
  rule_code: string;
  rule_name: string;
  severity: Severity;
  segment_id: string | null;
  quote: string | null;
  start_s: number | null;
  explanation: string;
  confidence: number;
  detected_by: DetectedBy;
  reviewer_status: ReviewerStatus;
}

export interface Rule {
  code: string;
  name: string;
  description: string;
  rbi_reference: string;
  severity: Severity;
  detection: string;
  enabled: boolean;
}

export interface CallDetail extends Call {
  segments: Segment[];
  violations: Violation[];
  roles_look_correct: boolean;
  analysis_notice: string | null;
  transcription: { model: string; language_code: string; format: string | null } | null;
}

export interface UploadMetadata {
  filename: string;
  agent_id?: string;
  agent_name?: string;
  called_at: string;
  language: Language;
  loan_ref: string;
  borrower_requested_time?: boolean;
}

export interface OverviewStats {
  as_of: string;
  calls_audited: number;
  calls_with_violations: number;
  calls_with_violations_pct: number;
  critical_flags: number;
  avg_score: number | null;
  calls_pending: number;
  violations_per_day: { date: string; critical: number; high: number; medium: number }[]; // last 14 days, oldest first
  top_rules: { rule_code: string; rule_name: string; count: number; pct_of_calls: number }[];
  agents_needing_review: {
    agent_id: string;
    agent_name: string;
    calls: number;
    avg_score: number;
    critical_flags: number;
  }[];
  recent_critical: {
    violation_id: string;
    call_id: string;
    agent_name: string;
    called_at: string;
    rule_code: string;
    rule_name: string;
    quote: string | null;
    start_s: number | null;
  }[];
}

export interface AgentDetail extends Agent {
  score_trend: { date: string; avg_score: number; calls: number }[];
  violations_by_rule: { rule_code: string; rule_name: string; count: number }[];
  calls: Call[];
}

export interface PRF {
  precision: number;
  recall: number;
  f1: number;
}

export interface EvalRun {
  id: string;
  run_at: string;
  config: "rules_only" | "rules_plus_llm";
  prompt_version: string;
  models: { stt: string; llm: string };
  n_calls: number;
  overall: PRF;
  rule_level_recall: number;
  timestamp_accuracy: number;
  clean_calls_flagged: number;
  clean_calls_total: number;
  role_mapping_accuracy: number;
  per_rule: Record<string, PRF & { tp: number; fp: number; fn: number }>;
  per_slice: Record<string, PRF & { n_calls: number }>; // keys: all, dev, test, hinglish, marathi, noisy, not_noisy
  failures: { test_key: string; rule_code: string; kind: "fp" | "fn"; note: string }[];
}

// ---- Request-side helpers (not in the plan's type list; used by the client interface) ----

export type CallSortKey =
  | "id"
  | "agent_name"
  | "called_at"
  | "duration_s"
  | "language"
  | "status"
  | "score"
  | "violations_count";

export interface ListCallsParams {
  page?: number;
  page_size?: number;
  q?: string;
  agent_id?: string;
  language?: Language;
  status?: CallStatus;
  severity?: Severity;
  rule_code?: string;
  date_from?: string; // yyyy-mm-dd, IST
  date_to?: string;
  sort?: CallSortKey;
  order?: "asc" | "desc";
}

export interface AudioUrl {
  url: string;
  expires_at: string;
}

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}
