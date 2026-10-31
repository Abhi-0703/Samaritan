import type { Call, CallDetail, DetectedBy, Language, ReviewerStatus, Segment, Violation } from "../types";
import { istMinutes } from "../format";
import { AGENT_NAMES } from "./agents";
import { FEATURED, type SegSpec, type VioSpec } from "./featured";
import {
  AMOUNTS,
  BORROWER_NAMES,
  BORROWER_REACTIONS_HINGLISH,
  BORROWER_REACTIONS_MARATHI,
  HINGLISH_BANK,
  HINGLISH_DAYS,
  HINGLISH_EXCUSES,
  MARATHI_BANK,
  MARATHI_FILLER,
  MARATHI_OPENING,
  MARATHI_TAIL,
} from "./phrases";
import { int, mulberry32, pick, weighted, type Rng } from "./rng";
import { RULES } from "./rules";

export const AUDIO_FILES = [
  { url: "/audio/call-a.wav", duration_s: 105 },
  { url: "/audio/call-b.wav", duration_s: 140 },
  { url: "/audio/call-c.wav", duration_s: 180 },
] as const;

export function audioFor(duration_s: number | null): string {
  const d = duration_s ?? 0;
  return (AUDIO_FILES.find((f) => f.duration_s >= d) ?? AUDIO_FILES[AUDIO_FILES.length - 1]).url;
}

export interface Resolved {
  segments: Segment[];
  violations: Violation[];
}

/** What a call will contain once processing finishes. Pending calls keep this until then. */
export interface CallPlan {
  segs: SegSpec[];
  vios: VioSpec[];
  no_llm: boolean;
  swap_roles: boolean;
}

export interface StoredCall {
  call: Call;
  plan: CallPlan | null; // set while the call is not yet processed
  segments: Segment[];
  violations: Violation[];
  roles_look_correct: boolean;
  analysis_notice: string | null;
  transcription: CallDetail["transcription"];
  audio_url: string;
}

const NO_LLM_NOTICE = "Analysed without LLM: the language model was unavailable, so only keyword rules were applied.";

export const TRANSCRIPTION_INFO = (language: Language) => ({
  model: "gnani-prisma-v3.0",
  language_code: language === "marathi" ? "mr-IN,en-IN" : "hi-IN,en-IN",
  format: "transcribe",
});

const ruleName = (code: string) => RULES.find((r) => r.code === code)?.name ?? code;
const ruleSeverity = (code: string) => RULES.find((r) => r.code === code)!.severity;

/** Lay out segment timings so the transcript fits the audio length. */
export function layoutSegments(callId: string, specs: SegSpec[], duration_s: number): Segment[] {
  const raw = specs.map((s) => 1.6 + s.text.length / 13);
  const gap = 0.5;
  const total = raw.reduce((a, b) => a + b, 0) + gap * specs.length;
  const scale = (duration_s - 6) / total;
  let t = 2;
  return specs.map((s, index) => {
    const start = t;
    const end = start + raw[index] * scale;
    t = end + gap * scale;
    return {
      id: `${callId}-s${index}`,
      index,
      speaker: s.speaker,
      start_s: Math.round(start * 10) / 10,
      end_s: Math.round(end * 10) / 10,
      text: s.text,
    };
  });
}

function v1Spec(called_at: string): VioSpec {
  const hh = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false }).format(
    new Date(called_at),
  );
  return {
    rule: "V1",
    seg: null,
    quote: null,
    explanation: `The call started at ${hh} IST, outside the permitted window of 08:00 to 19:00, and the borrower did not ask for that time.`,
    confidence: 1,
    detected_by: "metadata",
  };
}

export function isAfterHours(called_at: string): boolean {
  const m = istMinutes(called_at);
  return m < 8 * 60 || m > 19 * 60;
}

export function resolvePlan(call: Call, plan: CallPlan): Resolved {
  const segs = plan.swap_roles
    ? plan.segs.map((s) => ({ ...s, speaker: s.speaker === "agent" ? ("borrower" as const) : ("agent" as const) }))
    : plan.segs;
  const segments = layoutSegments(call.id, segs, call.duration_s ?? 120);
  const vios: VioSpec[] = [...plan.vios];
  if (isAfterHours(call.called_at) && !call.borrower_requested_time && !vios.some((v) => v.rule === "V1")) {
    vios.unshift(v1Spec(call.called_at));
  }
  const violations: Violation[] = vios.map((v, n) => {
    const segment = v.seg === null ? null : segments[v.seg];
    if (segment && v.quote && !segment.text.includes(v.quote)) {
      throw new Error(`Mock data error: quote not found in ${call.id} segment ${v.seg}: ${v.quote}`);
    }
    return {
      id: `${call.id}-v${n}`,
      call_id: call.id,
      rule_code: v.rule,
      rule_name: ruleName(v.rule),
      severity: ruleSeverity(v.rule),
      segment_id: segment?.id ?? null,
      quote: v.quote,
      start_s: v.rule === "V8" ? 0 : (segment?.start_s ?? null),
      explanation: v.explanation,
      confidence: plan.no_llm && v.detected_by !== "metadata" ? Math.min(v.confidence, 0.7) : v.confidence,
      detected_by: plan.no_llm && v.detected_by !== "metadata" ? ("rules" as DetectedBy) : v.detected_by,
      reviewer_status: v.reviewer ?? "open",
    };
  });
  return { segments, violations };
}

// ---------------------------------------------------------------------------------------------
// Generated calls
// ---------------------------------------------------------------------------------------------

const FEMALE_AGENTS = new Set(["Sneha Kulkarni", "Pooja Yadav", "Kavita Joshi"]);

const AGENT_NAME_MR: Record<string, string> = {
  "Rohit Patil": "रोहित पाटील",
  "Sneha Kulkarni": "स्नेहा कुलकर्णी",
  "Imran Shaikh": "इमरान शेख",
  "Pooja Yadav": "पूजा यादव",
  "Aakash Verma": "आकाश वर्मा",
  "Kavita Joshi": "कविता जोशी",
};

const BORROWER_NAMES_MR = ["गणेश पवार", "महेश साळुंखे", "मंगेश देशमुख", "प्रदीप माने", "अंजली फडके", "सुरेश गायकवाड", "किशोर वाघमारे", "वैशाली जगताप"];

export interface PlannedViolation {
  rule: string;
  entry: number;
  reviewer: ReviewerStatus;
  confidence: number;
}

export function buildGeneratedPlan(
  rng: Rng,
  language: Language,
  agent: string,
  borrower: string,
  amount: number,
  planned: PlannedViolation[],
  opts: { no_llm?: boolean; swap_roles?: boolean } = {},
): CallPlan {
  const first = borrower.split(" ")[0];
  const female = FEMALE_AGENTS.has(agent);
  const segs: SegSpec[] = [];
  const vios: VioSpec[] = [];
  const bank = language === "marathi" ? MARATHI_BANK : HINGLISH_BANK;
  const reactions = language === "marathi" ? BORROWER_REACTIONS_MARATHI : BORROWER_REACTIONS_HINGLISH;
  const v8 = planned.find((p) => p.rule === "V8");
  const v6 = planned.find((p) => p.rule === "V6");
  const lineVios = planned.filter((p) => p.rule !== "V8" && p.rule !== "V1" && p.rule !== "V6");

  const addViolation = (p: PlannedViolation) => {
    const entry = bank[p.rule][p.entry % bank[p.rule].length];
    segs.push({ speaker: "agent", text: `${entry.lead} ${entry.quote}.` });
    vios.push({
      rule: p.rule,
      seg: segs.length - 1,
      quote: entry.quote,
      explanation: entry.explanation,
      confidence: p.confidence,
      detected_by: entry.detected_by,
      reviewer: p.reviewer,
    });
    segs.push({ speaker: "borrower", text: pick(rng, reactions) });
  };

  if (language === "marathi") {
    segs.push({ speaker: "agent", text: MARATHI_OPENING(AGENT_NAME_MR[agent] ?? agent, pick(rng, BORROWER_NAMES_MR)) });
    segs.push(...MARATHI_FILLER);
    lineVios.forEach(addViolation);
    segs.push(...MARATHI_TAIL);
  } else if (v6) {
    segs.push({
      speaker: "agent",
      text: `Namaste, main ${agent} bol ${female ? "rahi" : "raha"} hoon Sahyog Finance se. Kya meri baat ${borrower} ji se ho rahi hai?`,
    });
    segs.push({ speaker: "borrower", text: "Nahi, main unka bhai bol raha hoon. Woh abhi bahar gaye hain." });
    addViolation(v6);
    segs.push({ speaker: "agent", text: "Aap unse keh dijiye ki call back kar lein. Dhanyavaad." });
    segs.push({ speaker: "borrower", text: "Ji, theek hai. Main bol dunga." });
  } else {
    segs.push({
      speaker: "agent",
      text: v8
        ? `Haan hello, ${first} bol rahe ho? Loan ke baare mein baat karni hai.`
        : `Namaste, main ${agent} bol ${female ? "rahi" : "raha"} hoon Sahyog Finance se. Kya meri baat ${borrower} ji se ho rahi hai?`,
    });
    segs.push({ speaker: "borrower", text: "Haan ji, boliye." });
    segs.push({
      speaker: "agent",
      text: `${first} ji, aapke personal loan ki EMI ${int(rng, 8, 40)} din se pending hai, ${amount} rupaye. Kab tak ho payega?`,
    });
    segs.push({ speaker: "borrower", text: pick(rng, HINGLISH_EXCUSES) });
    segs.push({ speaker: "agent", text: "Samajh sakta hoon. Kaunsa din pakka rahega, taaki main note kar loon?" });
    const day = pick(rng, HINGLISH_DAYS);
    segs.push({ speaker: "borrower", text: `${day} tak kar dunga.` });
    lineVios.forEach(addViolation);
    segs.push({ speaker: "agent", text: `Theek hai, main ${day} ki date note kar leta hoon. Payment link SMS kar deta hoon.` });
    segs.push({ speaker: "borrower", text: "Theek hai, bhej dijiye." });
    segs.push({ speaker: "agent", text: `Dhanyavaad ${first} ji. Aapka din accha rahe.` });
  }

  if (v8) {
    vios.push({
      rule: "V8",
      seg: null,
      quote: null,
      explanation: "The agent did not state their own name or the lender's name in the first 60 seconds.",
      confidence: v8.confidence,
      detected_by: "both",
      reviewer: v8.reviewer,
    });
  }
  return { segs, vios, no_llm: !!opts.no_llm, swap_roles: !!opts.swap_roles };
}

/** Plan for a freshly uploaded call. Deterministic per loan reference so repeated demos behave the same. */
export function planForUpload(seed: number, language: Language, agent: string, loan_ref: string): CallPlan {
  const rng = mulberry32(seed);
  const borrower = pick(rng, BORROWER_NAMES);
  const planned: PlannedViolation[] = [];
  if (rng() < 0.6) {
    const pool = language === "marathi" ? ["V2", "V4", "V5", "V9"] : ["V2", "V3", "V4", "V5", "V7", "V8", "V9"];
    const rule = pick(rng, pool);
    planned.push({ rule, entry: int(rng, 0, 2), reviewer: "open", confidence: 0.7 + rng() * 0.25 });
  }
  void loan_ref;
  return buildGeneratedPlan(rng, language, agent, borrower, pick(rng, AMOUNTS), planned);
}

const AFTER_HOURS_TIMES = ["07:12", "07:48", "19:25", "20:10", "20:45", "21:15", "21:50"];
const REQUESTED_TIMES = ["19:40", "20:30"];

function istIso(daysAgo: number, hhmm: string, nowMs: number): string {
  const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(nowMs - daysAgo * 86_400_000),
  );
  return `${dayKey}T${hhmm}:00+05:30`;
}

const loanRef = (rng: Rng) => `SF-PL-${int(rng, 100000, 999999)}`;

export function agentIdFor(name: string): string {
  return `AG-${(AGENT_NAMES as readonly string[]).indexOf(name) + 1}`;
}

interface Draft {
  call: Omit<Call, "id">;
  plan: CallPlan | null;
  audio_url: string;
  roles_look_correct: boolean;
  analysis_notice: string | null;
}

/** Seeded dataset: 6 featured calls, ~48 other finished calls, 2 failed and 4 in progress. */
export function buildInitialCalls(nowMs: number): StoredCall[] {
  const rng = mulberry32(20261101);
  const drafts: Draft[] = [];

  // Featured calls with hand-written transcripts.
  for (const f of FEATURED) {
    drafts.push({
      call: {
        test_key: f.test_key,
        agent_id: agentIdFor(f.agent),
        agent_name: f.agent,
        loan_ref: f.loan_ref,
        called_at: istIso(f.days_ago, f.ist_time, nowMs),
        duration_s: f.duration_s,
        language: f.language,
        status: "done",
        score: null,
        violations_count: 0,
        max_severity: null,
        error: null,
        borrower_requested_time: false,
      },
      plan: { segs: f.segments, vios: f.violations, no_llm: false, swap_roles: false },
      audio_url: audioFor(f.duration_s),
      roles_look_correct: true,
      analysis_notice: null,
    });
  }

  const violationProb: Record<string, number> = {
    "Rohit Patil": 0.34, "Sneha Kulkarni": 0.14, "Imran Shaikh": 0.62, "Pooja Yadav": 0.2, "Aakash Verma": 0.55, "Kavita Joshi": 0.1,
  };
  const ruleWeights: (readonly [string, number])[] = [
    ["V2", 12], ["V3", 7], ["V4", 12], ["V5", 14], ["V6", 7], ["V7", 8], ["V8", 17], ["V9", 21],
  ];

  const TOTAL_GENERATED = 54;
  const afterHoursAt = new Set([2, 9, 15, 21, 28, 34, 41]);
  const requestedAt = new Set([12, 30]);
  const failedAt = new Set([7, 39]);
  const pendingAt = new Set([50, 51, 52, 53]);
  const noLlmAt = 19;
  const swappedAt = 26;
  const marathiEvery = 4; // roughly one call in four

  for (let i = 0; i < TOTAL_GENERATED; i++) {
    const pending = pendingAt.has(i);
    const language: Language = i % marathiEvery === 1 ? "marathi" : "hinglish";
    const agent = pick(rng, AGENT_NAMES);
    const borrower = pick(rng, BORROWER_NAMES);
    const duration = int(rng, 62, 178);
    const requested = requestedAt.has(i);
    let time = `${int(rng, 9, 18).toString().padStart(2, "0")}:${int(rng, 0, 59).toString().padStart(2, "0")}`;
    if (afterHoursAt.has(i)) time = AFTER_HOURS_TIMES[[...afterHoursAt].indexOf(i) % AFTER_HOURS_TIMES.length];
    if (requested) time = REQUESTED_TIMES[[...requestedAt].indexOf(i) % REQUESTED_TIMES.length];

    let called_at: string;
    if (pending) {
      // Recent calls that are still being processed.
      called_at = new Date(nowMs - (i - 49) * 70_000 - 40_000).toISOString();
    } else {
      called_at = istIso(1 + (i % 13), time, nowMs);
    }

    const planned: PlannedViolation[] = [];
    if (rng() < (violationProb[agent] ?? 0.3) * 0.75 && !failedAt.has(i)) {
      const count = rng() < 0.3 ? 2 : 1;
      const used = new Set<string>();
      for (let k = 0; k < count; k++) {
        let rule = weighted(rng, ruleWeights);
        if (language === "marathi") rule = pick(rng, ["V2", "V4", "V5", "V9"]);
        if (used.has(rule)) continue;
        used.add(rule);
        const r = rng();
        const reviewer: ReviewerStatus = r < 0.18 ? "confirmed" : r < 0.26 ? "dismissed" : "open";
        planned.push({ rule, entry: int(rng, 0, 2), reviewer, confidence: Math.round((0.62 + rng() * 0.35) * 100) / 100 });
      }
    }

    const status = pending ? (["queued", "transcribing", "analysing", "analysing"] as const)[i - 50] : failedAt.has(i) ? "failed" : "done";
    const plan = buildGeneratedPlan(rng, language, agent, borrower, pick(rng, AMOUNTS), planned, {
      no_llm: i === noLlmAt,
      swap_roles: i === swappedAt,
    });

    drafts.push({
      call: {
        test_key: null,
        agent_id: agentIdFor(agent),
        agent_name: agent,
        loan_ref: loanRef(rng),
        called_at,
        duration_s: status === "queued" || status === "transcribing" ? null : duration,
        language,
        status,
        score: null,
        violations_count: 0,
        max_severity: null,
        error:
          status === "failed"
            ? i === 7
              ? "Gnani job START_FAILED: the audio file contains no detectable speech."
              : "Analysis failed: the language model returned invalid JSON twice and the fallback provider timed out."
            : null,
        borrower_requested_time: requested,
      },
      plan: status === "done" ? plan : { ...plan },
      audio_url: audioFor(duration),
      roles_look_correct: i !== swappedAt,
      analysis_notice: i === noLlmAt ? NO_LLM_NOTICE : null,
    });
  }

  drafts.sort((a, b) => new Date(a.call.called_at).getTime() - new Date(b.call.called_at).getTime());

  return drafts.map((d, n) => {
    const id = `CL-${2101 + n}`;
    const call: Call = { ...d.call, id };
    const stored: StoredCall = {
      call,
      plan: d.plan,
      segments: [],
      violations: [],
      roles_look_correct: d.roles_look_correct,
      analysis_notice: d.analysis_notice,
      transcription: call.status === "queued" || call.status === "transcribing" || call.status === "failed" ? null : TRANSCRIPTION_INFO(call.language),
      audio_url: d.audio_url,
    };
    if (call.status === "done" && d.plan) {
      const resolved = resolvePlan(call, d.plan);
      stored.segments = resolved.segments;
      stored.violations = resolved.violations;
      stored.plan = null;
    }
    return stored;
  });
}

export { NO_LLM_NOTICE };
