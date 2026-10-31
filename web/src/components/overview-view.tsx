"use client";

import Link from "next/link";
import { Upload } from "lucide-react";
import { RuleCode, ScoreBadge } from "@/components/badges";
import { ViolationsPerDayChart } from "@/components/charts";
import { createColumns, DataTable } from "@/components/data-table";
import { KpiCard } from "@/components/kpi-card";
import { PageContent, PageHeader, Section } from "@/components/page-header";
import { BlockSkeleton, ErrorState } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatClock, formatDateTime, formatNumber } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { OverviewStats } from "@/lib/types";
import { cn } from "@/lib/utils";

type RuleRow = OverviewStats["top_rules"][number];
type AgentRow = OverviewStats["agents_needing_review"][number];
type CriticalRow = OverviewStats["recent_critical"][number];

const ruleCols = createColumns<RuleRow>();
const ruleColumns = ruleCols.columns([
  ruleCols.display({
    id: "rule",
    header: "Rule",
    cell: ({ row }) => (
      <span className="flex items-center gap-2">
        <RuleCode code={row.original.rule_code} />
        <span>{row.original.rule_name}</span>
      </span>
    ),
  }),
  ruleCols.display({ id: "count", header: "Violations", cell: ({ row }) => <span className="tnum">{row.original.count}</span> }),
  ruleCols.display({ id: "pct", header: "% of calls", cell: ({ row }) => <span className="tnum">{row.original.pct_of_calls.toFixed(1)}%</span> }),
]);

const agentCols = createColumns<AgentRow>();
const agentColumns = agentCols.columns([
  agentCols.display({ id: "agent", header: "Agent", cell: ({ row }) => <span className="font-medium">{row.original.agent_name}</span> }),
  agentCols.display({ id: "calls", header: "Calls", cell: ({ row }) => <span className="tnum">{row.original.calls}</span> }),
  agentCols.display({ id: "critical", header: "Critical flags", cell: ({ row }) => <span className="tnum">{row.original.critical_flags}</span> }),
  agentCols.display({ id: "score", header: "Avg score", cell: ({ row }) => <ScoreBadge score={row.original.avg_score} /> }),
]);

const critCols = createColumns<CriticalRow>();
const critColumns = critCols.columns([
  critCols.display({ id: "time", header: "Called at (IST)", cell: ({ row }) => <span className="tnum whitespace-nowrap">{formatDateTime(row.original.called_at)}</span> }),
  critCols.display({ id: "agent", header: "Agent", cell: ({ row }) => <span className="whitespace-nowrap">{row.original.agent_name}</span> }),
  critCols.display({
    id: "rule",
    header: "Rule",
    cell: ({ row }) => (
      <span className="flex items-center gap-2 whitespace-nowrap">
        <RuleCode code={row.original.rule_code} />
        <span>{row.original.rule_name}</span>
      </span>
    ),
  }),
  critCols.display({
    id: "quote",
    header: "Quote",
    cell: ({ row }) => {
      const r = row.original;
      return (
        <span className="line-clamp-1 max-w-[360px] text-muted-foreground">
          {r.start_s !== null && <span className="tnum mr-2 font-mono text-xs text-foreground">{formatClock(r.start_s)}</span>}
          {r.quote ? `“${r.quote}”` : "Call metadata"}
        </span>
      );
    },
  }),
]);

export function OverviewView() {
  const { data, error, loading, reload } = useAsync(() => api.getOverview(), "overview");

  return (
    <>
      <PageHeader
        title="Overview"
        description="Compliance across audited recovery calls in the last 14 days."
        actions={
          <Link href="/calls?upload=1" className={cn(buttonVariants({ size: "default" }))}>
            <Upload aria-hidden data-icon="inline-start" />
            Upload calls
          </Link>
        }
      />
      <PageContent>
        {error && !data ? (
          <ErrorState message={error.message} onRetry={reload} />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <KpiCard label="Calls audited" loading={loading} value={data && formatNumber(data.calls_audited)} sub="Finished calls" />
              <KpiCard
                label="Calls with violations"
                loading={loading}
                value={data && formatNumber(data.calls_with_violations)}
                sub={data && `${data.calls_with_violations_pct.toFixed(1)}% of audited calls`}
              />
              <KpiCard label="Critical flags" loading={loading} value={data && formatNumber(data.critical_flags)} sub="Last 14 days" />
              <KpiCard
                label="Average compliance score"
                loading={loading}
                value={data?.avg_score != null ? Math.round(data.avg_score) : "-"}
                sub="Out of 100"
              />
              <KpiCard label="Calls pending" loading={loading} value={data && formatNumber(data.calls_pending)} sub="Queued or processing" />
            </div>

            <Section title="Violations per day" description="Non-dismissed flags on calls from the last 14 days, by severity.">
              <div className="rounded-lg border p-4">
                {loading || !data ? <BlockSkeleton className="h-64" /> : <ViolationsPerDayChart data={data.violations_per_day} />}
              </div>
            </Section>

            <div className="grid gap-6 lg:grid-cols-2">
              <Section title="Most frequent violations">
                <div className="overflow-hidden rounded-lg border">
                  <DataTable
                    label="Most frequent violations"
                    data={data?.top_rules ?? []}
                    columns={ruleColumns}
                    getRowId={(r) => r.rule_code}
                    rowHref={(r) => `/calls?rule_code=${r.rule_code}`}
                    loading={loading}
                    skeletonRows={5}
                    empty={{ title: "No violations yet", description: "Flags appear here once calls are audited." }}
                  />
                </div>
              </Section>
              <Section title="Agents needing review" description="The five lowest average scores.">
                <div className="overflow-hidden rounded-lg border">
                  <DataTable
                    label="Agents needing review"
                    data={data?.agents_needing_review ?? []}
                    columns={agentColumns}
                    getRowId={(r) => r.agent_id}
                    rowHref={(r) => `/agents/${r.agent_id}`}
                    loading={loading}
                    skeletonRows={5}
                    empty={{ title: "No agents yet" }}
                  />
                </div>
              </Section>
            </div>

            <Section title="Recent critical flags" description="Select a row to open the call at that moment.">
              <div className="overflow-hidden rounded-lg border">
                <DataTable
                  label="Recent critical flags"
                  minWidth={760}
                  data={data?.recent_critical ?? []}
                  columns={critColumns}
                  getRowId={(r) => r.violation_id}
                  rowHref={(r) => `/calls/${r.call_id}${r.start_s !== null ? `?t=${Math.floor(r.start_s)}` : ""}`}
                  loading={loading}
                  skeletonRows={5}
                  empty={{ title: "No critical flags", description: "Critical violations from audited calls appear here." }}
                />
              </div>
            </Section>
          </>
        )}
      </PageContent>
    </>
  );
}
