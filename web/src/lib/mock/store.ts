import { istDayKey } from "../format";
import {
  ApiError,
  type Agent,
  type AgentDetail,
  type Call,
  type CallDetail,
  type CallStatus,
  type ListCallsParams,
  type OverviewStats,
  type Paginated,
  type ReviewerStatus,
  type Rule,
  type Severity,
  type UploadMetadata,
  type Violation,
} from "../types";
import { AGENT_NAMES, AGENT_TEAMS } from "./agents";
import {
  NO_LLM_NOTICE,
  TRANSCRIPTION_INFO,
  agentIdFor,
  audioFor,
  buildInitialCalls,
  planForUpload,
  resolvePlan,
  type StoredCall,
} from "./build";
import { buildEvalRuns } from "./eval";
import { hashString } from "./rng";
import { RULES } from "./rules";

const SCORE_WEIGHT: Record<Severity, number> = { critical: 30, high: 15, medium: 5 };
const SEVERITY_RANK: Record<Severity, number> = { critical: 3, high: 2, medium: 1 };

interface AgentRecord {
  id: string;
  name: string;
  team: string;
}

class MockDb {
  calls: StoredCall[];
  agents: AgentRecord[];
  rules: Rule[];
  evals;
  private nextCallNumber: number;
  private nextAgentNumber: number;

  constructor(readonly nowMs: number) {
    this.calls = buildInitialCalls(nowMs);
    this.agents = AGENT_NAMES.map((name, i) => ({ id: `AG-${i + 1}`, name, team: AGENT_TEAMS[name] }));
    this.rules = RULES.map((r) => ({ ...r }));
    this.evals = buildEvalRuns(nowMs);
    this.nextCallNumber = 2101 + this.calls.length;
    this.nextAgentNumber = AGENT_NAMES.length + 1;
    // Calls that were in flight when the dataset was seeded finish over the next few seconds.
    this.calls
      .filter((c) => !isTerminal(c.call.status))
      .forEach((c, i) => this.schedule(c.call.id, c.call.status, 1500 + i * 2500));
  }

  // ---- scoring (mirrors api/app/config/scoring.yaml) -------------------------------------

  private enabled(code: string): boolean {
    return this.rules.find((r) => r.code === code)?.enabled ?? true;
  }

  /** Violations of enabled rules that the reviewer has not dismissed. These drive scores and counts. */
  active(sc: StoredCall): Violation[] {
    return sc.violations.filter((v) => this.enabled(v.rule_code) && v.reviewer_status !== "dismissed");
  }

  scoreOf(sc: StoredCall): number {
    return Math.max(0, 100 - this.active(sc).reduce((s, v) => s + SCORE_WEIGHT[v.severity], 0));
  }

  toCall(sc: StoredCall): Call {
    if (sc.call.status !== "done") {
      return { ...sc.call, score: null, violations_count: 0, max_severity: null };
    }
    const active = this.active(sc);
    const max = active.reduce<Severity | null>(
      (m, v) => (m === null || SEVERITY_RANK[v.severity] > SEVERITY_RANK[m] ? v.severity : m),
      null,
    );
    return { ...sc.call, score: this.scoreOf(sc), violations_count: active.length, max_severity: max };
  }

  toDetail(sc: StoredCall): CallDetail {
    const visible = sc.violations
      .filter((v) => this.enabled(v.rule_code))
      .sort((a, b) => (a.start_s ?? -1) - (b.start_s ?? -1))
      .map((v) => ({ ...v }));
    return {
      ...this.toCall(sc),
      segments: sc.segments.map((s) => ({ ...s })),
      violations: visible,
      roles_look_correct: sc.roles_look_correct,
      analysis_notice: sc.analysis_notice,
      transcription: sc.transcription,
    };
  }

  find(id: string): StoredCall {
    const sc = this.calls.find((c) => c.call.id === id);
    if (!sc) throw new ApiError("not_found", `Call ${id} was not found.`);
    return sc;
  }

  // ---- pipeline simulation ------------------------------------------------------------------

  /** Moves a call through transcribing -> analysing -> done on a timer, like the real worker. */
  schedule(id: string, from: CallStatus, startDelayMs: number) {
    const steps: { status: CallStatus; after: number }[] = [];
    if (from === "queued") steps.push({ status: "transcribing", after: startDelayMs });
    if (from === "queued" || from === "transcribing") steps.push({ status: "analysing", after: from === "queued" ? 4500 : startDelayMs });
    if (from === "analysing") steps.push({ status: "done", after: startDelayMs });
    else steps.push({ status: "done", after: 4500 });
    let elapsed = 0;
    for (const step of steps) {
      elapsed += step.after;
      setTimeout(() => this.advance(id, step.status), elapsed);
    }
  }

  private advance(id: string, status: CallStatus) {
    const sc = this.calls.find((c) => c.call.id === id);
    if (!sc || sc.call.status === "failed") return;
    sc.call.status = status;
    if (status === "analysing") {
      sc.call.duration_s ??= 70 + (hashString(id) % 110);
      sc.transcription = TRANSCRIPTION_INFO(sc.call.language);
      sc.audio_url = audioFor(sc.call.duration_s);
    }
    if (status === "done" && sc.plan) {
      const resolved = resolvePlan(sc.call, sc.plan);
      sc.segments = resolved.segments;
      sc.violations = resolved.violations;
      sc.analysis_notice = sc.plan.no_llm ? NO_LLM_NOTICE : null;
      sc.plan = null;
    }
  }

  // ---- mutations ----------------------------------------------------------------------------

  upload(metadata: UploadMetadata[]): Call[] {
    return metadata.map((m) => {
      const agent = this.resolveAgent(m);
      const id = `CL-${this.nextCallNumber++}`;
      const call: Call = {
        id,
        test_key: null,
        agent_id: agent.id,
        agent_name: agent.name,
        loan_ref: m.loan_ref,
        called_at: m.called_at,
        duration_s: null,
        language: m.language,
        status: "queued",
        score: null,
        violations_count: 0,
        max_severity: null,
        error: null,
        borrower_requested_time: m.borrower_requested_time ?? false,
      };
      const sc: StoredCall = {
        call,
        plan: planForUpload(hashString(`${m.filename}${m.loan_ref}`), m.language, agent.name, m.loan_ref),
        segments: [],
        violations: [],
        roles_look_correct: true,
        analysis_notice: null,
        transcription: null,
        audio_url: audioFor(null),
      };
      this.calls.unshift(sc);
      this.schedule(id, "queued", 2500);
      return this.toCall(sc);
    });
  }

  private resolveAgent(m: UploadMetadata): AgentRecord {
    if (m.agent_id) {
      const a = this.agents.find((x) => x.id === m.agent_id);
      if (!a) throw new ApiError("not_found", "That agent does not exist.");
      return a;
    }
    const name = m.agent_name?.trim();
    if (!name) throw new ApiError("invalid_request", `Choose an agent for ${m.filename}.`);
    return this.agents.find((a) => a.name.toLowerCase() === name.toLowerCase()) ?? this.addAgent(name, "Collections");
  }

  addAgent(name: string, team: string): AgentRecord {
    const clean = name.trim();
    if (this.agents.some((a) => a.name.toLowerCase() === clean.toLowerCase())) {
      throw new ApiError("conflict", `An agent named ${clean} already exists.`);
    }
    const rec = { id: `AG-${this.nextAgentNumber++}`, name: clean, team: team.trim() || "Collections" };
    this.agents.push(rec);
    return rec;
  }

  retry(id: string): Call {
    const sc = this.find(id);
    if (!isTerminal(sc.call.status)) return this.toCall(sc);
    if (!sc.plan) {
      // Re-analysis of a finished call reuses its transcript.
      sc.plan = null;
      sc.call.status = "analysing";
      sc.call.error = null;
      this.schedule(id, "analysing", 3500);
      return this.toCall(sc);
    }
    sc.call.error = null;
    sc.call.status = "queued";
    this.schedule(id, "queued", 2500);
    return this.toCall(sc);
  }

  swapRoles(id: string): CallDetail {
    const sc = this.find(id);
    sc.segments = sc.segments.map((s) => ({
      ...s,
      speaker: s.speaker === "agent" ? "borrower" : s.speaker === "borrower" ? "agent" : "unknown",
    }));
    sc.roles_look_correct = true;
    return this.toDetail(sc);
  }

  review(violationId: string, status: ReviewerStatus): { violation: Violation; call_score: number } {
    for (const sc of this.calls) {
      const v = sc.violations.find((x) => x.id === violationId);
      if (v) {
        v.reviewer_status = status;
        return { violation: { ...v }, call_score: this.scoreOf(sc) };
      }
    }
    throw new ApiError("not_found", `Violation ${violationId} was not found.`);
  }

  setRule(code: string, enabled: boolean): Rule {
    const rule = this.rules.find((r) => r.code === code);
    if (!rule) throw new ApiError("not_found", `Rule ${code} was not found.`);
    rule.enabled = enabled;
    return { ...rule };
  }

  // ---- queries ------------------------------------------------------------------------------

  list(p: ListCallsParams): Paginated<Call> {
    const page = Math.max(1, p.page ?? 1);
    const page_size = p.page_size ?? 25;
    const q = p.q?.trim().toLowerCase();
    let rows = this.calls.map((sc) => ({ sc, call: this.toCall(sc) }));
    rows = rows.filter(({ sc, call }) => {
      if (q && !(call.id.toLowerCase().includes(q) || call.loan_ref.toLowerCase().includes(q) || (call.test_key ?? "").includes(q))) return false;
      if (p.agent_id && call.agent_id !== p.agent_id) return false;
      if (p.language && call.language !== p.language) return false;
      if (p.status && call.status !== p.status) return false;
      if (p.severity && !this.active(sc).some((v) => v.severity === p.severity)) return false;
      if (p.rule_code && !this.active(sc).some((v) => v.rule_code === p.rule_code)) return false;
      const day = istDayKey(call.called_at);
      if (p.date_from && day < p.date_from) return false;
      if (p.date_to && day > p.date_to) return false;
      return true;
    });
    const sort = p.sort ?? "called_at";
    const dir = (p.order ?? "desc") === "asc" ? 1 : -1;
    const key = (c: Call): string | number => {
      switch (sort) {
        case "id": return c.id;
        case "agent_name": return c.agent_name;
        case "called_at": return new Date(c.called_at).getTime();
        case "duration_s": return c.duration_s ?? -1;
        case "language": return c.language;
        case "status": return c.status;
        case "score": return c.score ?? -1;
        case "violations_count": return c.violations_count * 10 + (c.max_severity ? SEVERITY_RANK[c.max_severity] : 0);
      }
    };
    rows.sort((a, b) => {
      const x = key(a.call);
      const y = key(b.call);
      if (x === y) return new Date(b.call.called_at).getTime() - new Date(a.call.called_at).getTime();
      return (x < y ? -1 : 1) * dir;
    });
    const start = (page - 1) * page_size;
    return { items: rows.slice(start, start + page_size).map((r) => r.call), page, page_size, total: rows.length };
  }

  private doneCalls(): StoredCall[] {
    return this.calls.filter((c) => c.call.status === "done");
  }

  agentStats(agentId: string): Agent | null {
    const rec = this.agents.find((a) => a.id === agentId);
    if (!rec) return null;
    const done = this.doneCalls().filter((c) => c.call.agent_id === agentId);
    const scores = done.map((c) => this.scoreOf(c));
    const active = done.flatMap((c) => this.active(c));
    const counts = new Map<string, number>();
    active.forEach((v) => counts.set(v.rule_code, (counts.get(v.rule_code) ?? 0) + 1));
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
    return {
      id: rec.id,
      name: rec.name,
      team: rec.team,
      calls_count: done.length,
      avg_score: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
      critical_count: active.filter((v) => v.severity === "critical").length,
      violation_rate: done.length ? done.filter((c) => this.active(c).length > 0).length / done.length : 0,
      top_rule_code: top ? top[0] : null,
    };
  }

  agentDetail(agentId: string): AgentDetail {
    const base = this.agentStats(agentId);
    if (!base) throw new ApiError("not_found", `Agent ${agentId} was not found.`);
    const done = this.doneCalls().filter((c) => c.call.agent_id === agentId);
    const byDay = new Map<string, number[]>();
    for (const c of done) {
      const day = istDayKey(c.call.called_at);
      byDay.set(day, [...(byDay.get(day) ?? []), this.scoreOf(c)]);
    }
    const score_trend = [...byDay.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([date, s]) => ({ date, avg_score: s.reduce((a, b) => a + b, 0) / s.length, calls: s.length }));
    const byRule = new Map<string, number>();
    done.flatMap((c) => this.active(c)).forEach((v) => byRule.set(v.rule_code, (byRule.get(v.rule_code) ?? 0) + 1));
    const violations_by_rule = [...byRule.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([rule_code, count]) => ({ rule_code, rule_name: RULES.find((r) => r.code === rule_code)?.name ?? rule_code, count }));
    const calls = this.calls
      .filter((c) => c.call.agent_id === agentId)
      .map((c) => this.toCall(c))
      .sort((a, b) => (a.score ?? 101) - (b.score ?? 101));
    return { ...base, score_trend, violations_by_rule, calls };
  }

  overview(): OverviewStats {
    const done = this.doneCalls();
    const withViolations = done.filter((c) => this.active(c).length > 0);
    const allActive = done.flatMap((c) => this.active(c).map((v) => ({ v, sc: c })));
    const scores = done.map((c) => this.scoreOf(c));

    const days: string[] = [];
    for (let i = 13; i >= 0; i--) days.push(istDayKey(new Date(this.nowMs - i * 86_400_000)));
    const perDay = days.map((date) => ({ date, critical: 0, high: 0, medium: 0 }));
    for (const { v, sc } of allActive) {
      const row = perDay.find((d) => d.date === istDayKey(sc.call.called_at));
      if (row) row[v.severity] += 1;
    }

    const byRule = new Map<string, Set<string>>();
    const counts = new Map<string, number>();
    for (const { v, sc } of allActive) {
      counts.set(v.rule_code, (counts.get(v.rule_code) ?? 0) + 1);
      byRule.set(v.rule_code, (byRule.get(v.rule_code) ?? new Set()).add(sc.call.id));
    }
    const top_rules = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([rule_code, count]) => ({
        rule_code,
        rule_name: RULES.find((r) => r.code === rule_code)?.name ?? rule_code,
        count,
        pct_of_calls: done.length ? ((byRule.get(rule_code)?.size ?? 0) / done.length) * 100 : 0,
      }));

    const agents_needing_review = this.agents
      .map((a) => this.agentStats(a.id))
      .filter((a): a is Agent & { avg_score: number } => !!a && a.avg_score !== null)
      .sort((a, b) => a.avg_score - b.avg_score)
      .slice(0, 5)
      .map((a) => ({ agent_id: a.id, agent_name: a.name, calls: a.calls_count, avg_score: a.avg_score, critical_flags: a.critical_count }));

    const recent_critical = allActive
      .filter(({ v }) => v.severity === "critical")
      .sort((a, b) => new Date(b.sc.call.called_at).getTime() - new Date(a.sc.call.called_at).getTime())
      .slice(0, 6)
      .map(({ v, sc }) => ({
        violation_id: v.id,
        call_id: sc.call.id,
        agent_name: sc.call.agent_name,
        called_at: sc.call.called_at,
        rule_code: v.rule_code,
        rule_name: v.rule_name,
        quote: v.quote,
        start_s: v.start_s,
      }));

    return {
      as_of: new Date(this.nowMs).toISOString(),
      calls_audited: done.length,
      calls_with_violations: withViolations.length,
      calls_with_violations_pct: done.length ? (withViolations.length / done.length) * 100 : 0,
      critical_flags: allActive.filter(({ v }) => v.severity === "critical").length,
      avg_score: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
      calls_pending: this.calls.filter((c) => !isTerminal(c.call.status)).length,
      violations_per_day: perDay,
      top_rules,
      agents_needing_review,
      recent_critical,
    };
  }
}

function isTerminal(s: CallStatus): boolean {
  return s === "done" || s === "failed";
}

let db: MockDb | null = null;

/** Lazily created so nothing is generated, and no timers start, until a client component asks. */
export function getDb(): MockDb {
  db ??= new MockDb(Date.now());
  return db;
}

export { agentIdFor };
