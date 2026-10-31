"use client";

import { useState } from "react";
import { Info } from "lucide-react";
import { RuleCode } from "@/components/badges";
import { GroupedMetricsChart } from "@/components/charts";
import { createColumns, DataTable } from "@/components/data-table";
import { KpiCard } from "@/components/kpi-card";
import { PageContent, PageHeader, Section } from "@/components/page-header";
import { BlockSkeleton, EmptyState, ErrorState } from "@/components/states";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api } from "@/lib/api";
import { formatDateTime, formatPct } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { EvalRun, PRF } from "@/lib/types";

const SLICES = [
  { key: "all", label: "All 30 calls" },
  { key: "test", label: "Held-out test (20)" },
  { key: "hinglish", label: "Hinglish" },
  { key: "marathi", label: "Marathi" },
  { key: "noisy", label: "Noisy audio" },
] as const;

type RuleRow = { code: string; name: string; counts: EvalRun["per_rule"][string] };
const ruleCols = createColumns<RuleRow>();
const ruleColumns = ruleCols.columns([
  ruleCols.display({
    id: "rule",
    header: "Rule",
    cell: ({ row }) => (
      <span className="flex items-center gap-2 whitespace-nowrap">
        <RuleCode code={row.original.code} />
        <span>{row.original.name}</span>
      </span>
    ),
  }),
  ruleCols.display({ id: "p", header: "Precision", cell: ({ row }) => <span className="tnum">{formatPct(row.original.counts.precision)}</span> }),
  ruleCols.display({ id: "r", header: "Recall", cell: ({ row }) => <span className="tnum">{formatPct(row.original.counts.recall)}</span> }),
  ruleCols.display({ id: "f", header: "F1", cell: ({ row }) => <span className="tnum">{formatPct(row.original.counts.f1)}</span> }),
  ruleCols.display({ id: "tp", header: "TP", cell: ({ row }) => <span className="tnum">{row.original.counts.tp}</span> }),
  ruleCols.display({ id: "fp", header: "FP", cell: ({ row }) => <span className="tnum">{row.original.counts.fp}</span> }),
  ruleCols.display({ id: "fn", header: "FN", cell: ({ row }) => <span className="tnum">{row.original.counts.fn}</span> }),
]);

type Failure = EvalRun["failures"][number];
const failCols = createColumns<Failure>();
const failColumns = failCols.columns([
  failCols.display({ id: "call", header: "Call", cell: ({ row }) => <span className="font-mono text-xs">{row.original.test_key}</span> }),
  failCols.display({ id: "rule", header: "Rule", cell: ({ row }) => <RuleCode code={row.original.rule_code} /> }),
  failCols.display({ id: "kind", header: "Outcome", cell: ({ row }) => <span className="whitespace-nowrap">{row.original.kind === "fp" ? "False positive" : "Missed violation"}</span> }),
  failCols.display({ id: "note", header: "What happened", cell: ({ row }) => <span className="block max-w-[560px] py-2 text-muted-foreground">{row.original.note}</span> }),
]);

type CompareRow = { metric: string; only: number; plus: number };
const cmpCols = createColumns<CompareRow>();
const cmpColumns = cmpCols.columns([
  cmpCols.display({ id: "metric", header: "Metric", cell: ({ row }) => <span className="font-medium">{row.original.metric}</span> }),
  cmpCols.display({ id: "only", header: "Rules only", cell: ({ row }) => <span className="tnum">{formatPct(row.original.only, 1)}</span> }),
  cmpCols.display({ id: "plus", header: "Rules + LLM", cell: ({ row }) => <span className="tnum">{formatPct(row.original.plus, 1)}</span> }),
]);

const METRICS: [string, keyof PRF][] = [
  ["Precision", "precision"],
  ["Recall", "recall"],
  ["F1", "f1"],
];

export function AccuracyView() {
  const { data, error, loading, reload } = useAsync(() => api.getLatestEval(), "eval");
  const rules = useAsync(() => api.listRules(), "rules");
  const [slice, setSlice] = useState<(typeof SLICES)[number]["key"]>("test");

  const plus = data?.rules_plus_llm ?? null;
  const only = data?.rules_only ?? null;
  const sliceLabel = SLICES.find((s) => s.key === slice)?.label ?? "";

  const body = () => {
    if (loading) return <BlockSkeleton className="h-80" />;
    if (error && !data) return <ErrorState message={error.message} onRetry={reload} />;
    if (!plus || !only) {
      return <EmptyState title="No evaluation has been run yet" description="Run the evaluation on the labelled test calls to see precision and recall here." />;
    }
    const s = plus.per_slice[slice];
    const so = only.per_slice[slice];
    const compare: CompareRow[] = METRICS.map(([metric, k]) => ({ metric, only: so[k], plus: s[k] }));
    const perRule: RuleRow[] = Object.entries(plus.per_rule).map(([code, counts]) => ({
      code,
      name: rules.data?.find((r) => r.code === code)?.name ?? "",
      counts,
    }));

    return (
      <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ToggleGroup
            aria-label="Choose which calls to measure"
            variant="outline"
            spacing={0}
            value={[slice]}
            onValueChange={(v) => v[0] && setSlice(v[0] as typeof slice)}
          >
            {SLICES.map((x) => (
              <ToggleGroupItem key={x.key} value={x.key} className="data-pressed:bg-brand-subtle data-pressed:text-brand-text">
                {x.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p className="tnum text-xs text-muted-foreground">
            Run {formatDateTime(plus.run_at)} IST, prompt {plus.prompt_version}, {plus.models.llm}, {plus.models.stt}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <KpiCard label="Calls evaluated" value={s.n_calls} sub={sliceLabel} />
          <KpiCard label="Precision" value={formatPct(s.precision, 1)} sub="Of flags raised, share correct" />
          <KpiCard label="Recall" value={formatPct(s.recall, 1)} sub="Of real violations, share found" />
          <KpiCard label="F1" value={formatPct(s.f1, 1)} sub="Balance of the two" />
          <KpiCard label="Clean calls wrongly flagged" value={`${plus.clean_calls_flagged} of ${plus.clean_calls_total}`} sub="All 30 calls" />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Rules only compared with Rules + LLM" description={`${sliceLabel}. Same transcripts, so differences come from detection.`}>
            <div className="space-y-4 rounded-lg border p-4">
              <GroupedMetricsChart
                data={compare.map((c) => ({ metric: c.metric, rules_only: Math.round(c.only * 1000) / 10, rules_plus_llm: Math.round(c.plus * 1000) / 10 }))}
              />
              <div className="-mx-4 -mb-4 overflow-hidden border-t">
                <DataTable label="Rules only compared with Rules plus LLM" data={compare} columns={cmpColumns} getRowId={(r) => r.metric} />
              </div>
            </div>
          </Section>

          <Section title="Timing and speaker mapping" description="Measured on all 30 calls.">
            <div className="grid grid-cols-2 gap-4">
              <KpiCard label="Timestamp accuracy" value={formatPct(plus.timestamp_accuracy, 1)} sub="Correct flags within 5 s of the labelled moment" />
              <KpiCard label="Rule-level recall" value={formatPct(plus.rule_level_recall, 1)} sub="Right rule found, timing ignored" />
              <KpiCard label="Speaker roles mapped" value={formatPct(plus.role_mapping_accuracy, 1)} sub="Agent and borrower told apart" />
              <KpiCard label="Rules only: clean calls flagged" value={`${only.clean_calls_flagged} of ${only.clean_calls_total}`} sub="Baseline without the LLM" />
            </div>
          </Section>
        </div>

        <Section title="By rule" description="Rules + LLM on all 30 calls. TP true positive, FP false positive, FN missed.">
          <div className="overflow-hidden rounded-lg border">
            <DataTable label="Accuracy by rule" minWidth={640} data={perRule} columns={ruleColumns} getRowId={(r) => r.code} rightAligned={[]} />
          </div>
        </Section>

        <Section title="Known failure cases" description="Where the Rules + LLM run was wrong on the labelled calls.">
          <div className="overflow-hidden rounded-lg border">
            <DataTable
              label="Known failure cases"
              minWidth={720}
              data={plus.failures}
              columns={failColumns}
              getRowId={(f) => `${f.test_key}-${f.rule_code}-${f.kind}`}
              empty={{ title: "No failures recorded" }}
            />
          </div>
        </Section>

        <section className="max-w-3xl space-y-2 text-muted-foreground" aria-label="Methodology">
          <h2 className="font-semibold text-foreground">How these numbers are measured</h2>
          <p>
            Thirty acted calls, 22 in Hinglish and 8 in Marathi, were recorded from scripts and labelled by hand. Detection was tuned on the 10 development calls only; the 20
            held-out test calls were never used for tuning. A flag counts as correct when it names the right rule and falls within 5 seconds of the labelled moment, except
            for call-time and introduction flags, which match on the rule alone.
          </p>
          <p>Flags are decision support, not legal findings.</p>
        </section>
      </>
    );
  };

  return (
    <>
      <PageHeader title="Accuracy" description="Measured precision and recall on the labelled test calls." />
      <PageContent>
        {api.isMock && (
          <div role="note" className="flex items-start gap-2 rounded-lg border bg-surface p-3 text-muted-foreground">
            <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
            <p>These figures come from sample data while the app runs without a backend. Real figures replace them after the evaluation runs on the recorded calls.</p>
          </div>
        )}
        {body()}
      </PageContent>
    </>
  );
}
