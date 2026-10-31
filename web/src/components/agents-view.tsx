"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { RuleCode, ScoreBadge } from "@/components/badges";
import { createColumns, DataTable, type SortState } from "@/components/data-table";
import { PageContent, PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { formatPct } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { Agent } from "@/lib/types";

const cols = createColumns<Agent>();

const SORT_KEYS = {
  agent: "name",
  team: "team",
  calls: "calls_count",
  score: "avg_score",
  rate: "violation_rate",
  critical: "critical_count",
} as const;

export function AgentsView() {
  const { data, error, loading, reload } = useAsync(() => api.listAgents(), "agents");
  const rules = useAsync(() => api.listRules(), "rules");
  const [sort, setSort] = useState<SortState>({ key: "avg_score", order: "asc" });

  const columns = useMemo(
    () =>
      cols.columns([
        cols.display({
          id: "agent",
          header: "Agent",
          cell: ({ row }) => (
            <Link href={`/agents/${row.original.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
              {row.original.name}
            </Link>
          ),
        }),
        cols.display({ id: "team", header: "Team", cell: ({ row }) => <span className="whitespace-nowrap text-muted-foreground">{row.original.team}</span> }),
        cols.display({ id: "calls", header: "Calls audited", cell: ({ row }) => <span className="tnum">{row.original.calls_count}</span> }),
        cols.display({ id: "score", header: "Average score", cell: ({ row }) => <ScoreBadge score={row.original.avg_score} /> }),
        cols.display({ id: "rate", header: "Violation rate", cell: ({ row }) => <span className="tnum">{formatPct(row.original.violation_rate)}</span> }),
        cols.display({ id: "critical", header: "Critical flags", cell: ({ row }) => <span className="tnum">{row.original.critical_count}</span> }),
        cols.display({
          id: "top",
          header: "Most common violation",
          cell: ({ row }) => {
            const code = row.original.top_rule_code;
            if (!code) return <span className="text-muted-foreground">None</span>;
            return (
              <span className="flex items-center gap-2 whitespace-nowrap">
                <RuleCode code={code} />
                <span>{rules.data?.find((r) => r.code === code)?.name ?? ""}</span>
              </span>
            );
          },
        }),
      ]),
    [rules.data],
  );

  const sorted = useMemo(() => {
    const rows = [...(data ?? [])];
    const key = sort.key as keyof Agent;
    rows.sort((a, b) => {
      const x = a[key] ?? -1;
      const y = b[key] ?? -1;
      const cmp = typeof x === "string" && typeof y === "string" ? x.localeCompare(y) : Number(x) - Number(y);
      return sort.order === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [data, sort]);

  return (
    <>
      <PageHeader title="Agents" description="Scorecards for every agent whose calls were audited." />
      <PageContent>
        <div className="overflow-hidden rounded-lg border">
          <DataTable
            label="Agents"
            minWidth={880}
            data={sorted}
            columns={columns}
            getRowId={(a) => a.id}
            sortKeys={SORT_KEYS}
            sort={sort}
            onSortChange={(k) => setSort((s) => ({ key: k, order: s.key === k && s.order === "asc" ? "desc" : "asc" }))}
            rowHref={(a) => `/agents/${a.id}`}
            loading={loading}
            error={error}
            onRetry={reload}
            skeletonRows={6}
            empty={{ title: "No agents yet", description: "Agents appear when calls are uploaded." }}
          />
        </div>
      </PageContent>
    </>
  );
}
