import type { EvalRun, PRF } from "../types";

type Counts = { tp: number; fp: number; fn: number };

function prf({ tp, fp, fn }: Counts): PRF {
  const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
  const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
  const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
  return { precision, recall, f1 };
}

const sum = (list: Counts[]): Counts => ({
  tp: list.reduce((a, c) => a + c.tp, 0),
  fp: list.reduce((a, c) => a + c.fp, 0),
  fn: list.reduce((a, c) => a + c.fn, 0),
});

const c = (tp: number, fp: number, fn: number): Counts => ({ tp, fp, fn });

// 28 expected violations across the 30 labelled calls. Illustrative figures for the mock client only.
const PLUS_LLM_RULES: Record<string, Counts> = {
  V1: c(4, 0, 0), V2: c(3, 0, 0), V3: c(2, 1, 1), V4: c(3, 1, 0), V5: c(2, 0, 1),
  V6: c(1, 0, 2), V7: c(3, 0, 0), V8: c(3, 1, 0), V9: c(2, 0, 1),
};
const RULES_ONLY_RULES: Record<string, Counts> = {
  V1: c(4, 0, 0), V2: c(3, 2, 0), V3: c(2, 3, 1), V4: c(3, 3, 0), V5: c(1, 4, 2),
  V6: c(0, 1, 3), V7: c(2, 1, 1), V8: c(3, 2, 0), V9: c(2, 3, 1),
};

const PLUS_LLM_SLICES: Record<string, Counts & { n: number }> = {
  all: { ...c(23, 3, 5), n: 30 }, dev: { ...c(9, 1, 0), n: 10 }, test: { ...c(14, 2, 5), n: 20 },
  hinglish: { ...c(18, 2, 5), n: 22 }, marathi: { ...c(5, 1, 0), n: 8 },
  noisy: { ...c(6, 0, 1), n: 8 }, not_noisy: { ...c(17, 3, 4), n: 22 },
};
const RULES_ONLY_SLICES: Record<string, Counts & { n: number }> = {
  all: { ...c(20, 19, 8), n: 30 }, dev: { ...c(7, 6, 2), n: 10 }, test: { ...c(13, 13, 6), n: 20 },
  hinglish: { ...c(16, 15, 7), n: 22 }, marathi: { ...c(4, 4, 1), n: 8 },
  noisy: { ...c(5, 6, 2), n: 8 }, not_noisy: { ...c(15, 13, 6), n: 22 },
};

function build(
  id: string,
  config: EvalRun["config"],
  rules: Record<string, Counts>,
  slices: Record<string, Counts & { n: number }>,
  extra: Pick<EvalRun, "rule_level_recall" | "timestamp_accuracy" | "clean_calls_flagged" | "role_mapping_accuracy" | "failures">,
  runAt: string,
): EvalRun {
  const per_rule: EvalRun["per_rule"] = {};
  for (const [code, counts] of Object.entries(rules)) per_rule[code] = { ...prf(counts), ...counts };
  const per_slice: EvalRun["per_slice"] = {};
  for (const [key, { n, ...counts }] of Object.entries(slices)) per_slice[key] = { ...prf(counts), n_calls: n };
  return {
    id,
    run_at: runAt,
    config,
    prompt_version: "v3",
    models: { stt: "gnani-prisma-v3.0", llm: "openai/gpt-oss-120b" },
    n_calls: 30,
    overall: prf(sum(Object.values(rules))),
    clean_calls_total: 12,
    per_rule,
    per_slice,
    ...extra,
  };
}

export function buildEvalRuns(nowMs: number): { rules_only: EvalRun; rules_plus_llm: EvalRun } {
  const runAt = new Date(nowMs - 6 * 3_600_000).toISOString();
  return {
    rules_only: build(
      "EV-1002",
      "rules_only",
      RULES_ONLY_RULES,
      RULES_ONLY_SLICES,
      {
        rule_level_recall: 22 / 28,
        timestamp_accuracy: 20 / 22,
        clean_calls_flagged: 7,
        role_mapping_accuracy: 29 / 30,
        failures: [
          { test_key: "call_03", rule_code: "V7", kind: "fp", note: "The truthful 'legal recovery desk' introduction matched the keyword list; there was no false claim." },
          { test_key: "call_06", rule_code: "V4", kind: "fp", note: "A lawful mention of a legal notice and credit-bureau reporting matched 'notice' and 'legal'." },
          { test_key: "call_30", rule_code: "V5", kind: "fp", note: "The agent asked the borrower to confirm her own office address; 'office' matched the shaming list." },
          { test_key: "call_10", rule_code: "V6", kind: "fn", note: "A polite disclosure to a relative has no threatening keywords, so rules cannot see it." },
        ],
      },
      runAt,
    ),
    rules_plus_llm: build(
      "EV-1003",
      "rules_plus_llm",
      PLUS_LLM_RULES,
      PLUS_LLM_SLICES,
      {
        rule_level_recall: 25 / 28,
        timestamp_accuracy: 23 / 25,
        clean_calls_flagged: 1,
        role_mapping_accuracy: 29 / 30,
        failures: [
          { test_key: "call_15", rule_code: "V3", kind: "fp", note: "A courtesy visit by an executive during working hours was read as a menace." },
          { test_key: "call_14", rule_code: "V4", kind: "fp", note: "The same threat was flagged twice on adjacent segments; the second flag was counted as a false positive." },
          { test_key: "call_20", rule_code: "V8", kind: "fp", note: "The agent's name was transcribed in Devanagari, which did not match the lender alias list." },
          { test_key: "call_25", rule_code: "V3", kind: "fn", note: "An indirect menace about visiting the home with the children present was not recognised as a threat." },
          { test_key: "call_07", rule_code: "V5", kind: "fn", note: "The model paraphrased the quote, so evidence verification discarded a correct flag." },
          { test_key: "call_10", rule_code: "V6", kind: "fn", note: "A polite disclosure to a relative was judged as a call-back request." },
          { test_key: "call_28", rule_code: "V6", kind: "fn", note: "The disclosure was made without naming the lender, and the model judged the caller's role as unclear." },
          { test_key: "call_17", rule_code: "V9", kind: "fn", note: "The ultimatum was split across two segments and fell below the confidence threshold." },
        ],
      },
      runAt,
    ),
  };
}
