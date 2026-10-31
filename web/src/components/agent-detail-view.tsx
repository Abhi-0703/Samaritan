"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ScoreBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { ScoreTrendChart, ViolationsByRuleChart } from "@/components/charts";
import { createColumns, DataTable } from "@/components/data-table";
import { KpiCard } from "@/components/kpi-card";
import { PageContent, PageHeader, Section } from "@/components/page-header";
import { BlockSkeleton, EmptyState, ErrorState } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration, formatPct } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { Call } from "@/lib/types";

const cols = createColumns<Call>();
const columns = cols.columns([
  cols.display({
    id: "id",
    header: "Call",
    cell: ({ row }) => (
      <Link href={`/calls/${row.original.id}`} className="font-mono text-xs font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
        {row.original.id}
      </Link>
    ),
  }),
  cols.display({ id: "called_at", header: "Called at (IST)", cell: ({ row }) => <span className="tnum whitespace-nowrap">{formatDateTime(row.original.called_at)}</span> }),
  cols.display({ id: "duration", header: "Duration", cell: ({ row }) => <span className="tnum">{formatDuration(row.original.duration_s)}</span> }),
  cols.display({ id: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> }),
  cols.display({ id: "score", header: "Score", cell: ({ row }) => <ScoreBadge score={row.original.score} /> }),
  cols.display({
    id: "violations",
    header: "Violations",
    cell: ({ row }) =>
      row.original.status !== "done" ? (
        <span className="text-muted-foreground">-</span>
      ) : row.original.violations_count === 0 ? (
        <span className="text-muted-foreground">None</span>
      ) : (
        <span className="flex items-center gap-2">
          <span className="tnum">{row.original.violations_count}</span>
          {row.original.max_severity && <SeverityBadge severity={row.original.max_severity} />}
        </span>
      ),
  }),
]);

export function AgentDetailView({ id }: { id: string }) {
  const agent = useAsync(() => api.getAgent(id), id);
  const rules = useAsync(() => api.listRules(), "rules");

  const back = (
    <Link href="/agents" aria-label="Back to agents" className={buttonVariants({ variant: "ghost", size: "icon-sm" })}>
      <ArrowLeft aria-hidden />
    </Link>
  );

  if (agent.error && !agent.data) {
    return (
      <>
        <PageHeader title="Agent" back={back} />
        <PageContent>
          <ErrorState title="Could not open this agent" message={agent.error.message} onRetry={agent.reload} />
        </PageContent>
      </>
    );
  }

  const a = agent.data;
  const byRule = (a?.violations_by_rule ?? []).map((r) => ({
    ...r,
    severity: rules.data?.find((x) => x.code === r.rule_code)?.severity ?? "medium",
  }));

  return (
    <>
      <PageHeader title={a?.name ?? "Agent"} description={a?.team} back={back} />
      <PageContent>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Calls audited" loading={!a} value={a?.calls_count} />
          <KpiCard label="Average compliance score" loading={!a} value={a?.avg_score != null ? Math.round(a.avg_score) : "-"} sub="Out of 100" />
          <KpiCard label="Violation rate" loading={!a} value={a && formatPct(a.violation_rate)} sub="Calls with at least one flag" />
          <KpiCard label="Critical flags" loading={!a} value={a?.critical_count} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Score trend" description="Average compliance score of this agent's calls per day.">
            <div className="rounded-lg border p-4">
              {!a ? <BlockSkeleton className="h-56" /> : a.score_trend.length === 0 ? <EmptyState title="No scored calls yet" /> : <ScoreTrendChart data={a.score_trend} />}
            </div>
          </Section>
          <Section title="Violations by rule" description="Non-dismissed flags, coloured by rule severity.">
            <div className="rounded-lg border p-4">
              {!a ? <BlockSkeleton className="h-56" /> : byRule.length === 0 ? <EmptyState title="No violations" description="No rule was broken on this agent's audited calls." /> : <ViolationsByRuleChart data={byRule} />}
            </div>
          </Section>
        </div>

        <Section title="Calls" description="Lowest scores first.">
          <div className="overflow-hidden rounded-lg border">
            <DataTable
              label="Calls by this agent"
              minWidth={640}
              data={a?.calls ?? []}
              columns={columns}
              getRowId={(c) => c.id}
              rowHref={(c) => `/calls/${c.id}`}
              loading={!a}
              skeletonRows={6}
              empty={{ title: "No calls yet", description: "Calls appear once recordings for this agent are uploaded." }}
            />
          </div>
        </Section>
      </PageContent>
    </>
  );
}
