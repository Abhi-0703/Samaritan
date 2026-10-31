"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Search, Upload, X } from "lucide-react";
import { ScoreBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { createColumns, DataTable, Pagination, type SortState } from "@/components/data-table";
import { FilterSelect } from "@/components/filter-select";
import { PageContent, PageHeader } from "@/components/page-header";
import { UploadDrawer } from "@/components/upload-drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration, isTerminal } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { Call, CallSortKey, CallStatus, Language, ListCallsParams, Severity } from "@/lib/types";

const PAGE_SIZE = 25;
const POLL_MS = 5000;

const SORT_KEYS: Record<string, CallSortKey> = {
  id: "id",
  agent: "agent_name",
  called_at: "called_at",
  duration: "duration_s",
  language: "language",
  status: "status",
  score: "score",
  violations: "violations_count",
};

const cols = createColumns<Call>();
const columns = cols.columns([
  cols.display({
    id: "id",
    header: "Call",
    cell: ({ row }) => (
      <Link href={`/calls/${row.original.id}`} className="block leading-4 hover:underline" onClick={(e) => e.stopPropagation()}>
        <span className="font-mono text-xs font-medium">{row.original.id}</span>
        <span className="block font-mono text-xs text-muted-foreground">{row.original.loan_ref}</span>
      </Link>
    ),
  }),
  cols.display({ id: "agent", header: "Agent", cell: ({ row }) => <span className="whitespace-nowrap">{row.original.agent_name}</span> }),
  cols.display({
    id: "called_at",
    header: "Called at (IST)",
    cell: ({ row }) => <span className="tnum whitespace-nowrap">{formatDateTime(row.original.called_at)}</span>,
  }),
  cols.display({ id: "duration", header: "Duration", cell: ({ row }) => <span className="tnum whitespace-nowrap">{formatDuration(row.original.duration_s)}</span> }),
  cols.display({ id: "language", header: "Language", cell: ({ row }) => <span className="capitalize">{row.original.language}</span> }),
  cols.display({ id: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> }),
  cols.display({ id: "score", header: "Score", cell: ({ row }) => <ScoreBadge score={row.original.score} /> }),
  cols.display({
    id: "violations",
    header: "Violations",
    cell: ({ row }) => {
      const c = row.original;
      if (c.status !== "done") return <span className="text-muted-foreground">-</span>;
      if (c.violations_count === 0) return <span className="text-muted-foreground">None</span>;
      return (
        <span className="flex items-center gap-2">
          <span className="tnum">{c.violations_count}</span>
          {c.max_severity && <SeverityBadge severity={c.max_severity} />}
        </span>
      );
    },
  }),
]);

function parseParams(sp: URLSearchParams): ListCallsParams {
  const get = (k: string) => sp.get(k) ?? undefined;
  return {
    page: Number(get("page")) || 1,
    page_size: PAGE_SIZE,
    q: get("q"),
    agent_id: get("agent_id"),
    language: get("language") as Language | undefined,
    status: get("status") as CallStatus | undefined,
    severity: get("severity") as Severity | undefined,
    rule_code: get("rule_code"),
    date_from: get("date_from"),
    date_to: get("date_to"),
    sort: (get("sort") as CallSortKey | undefined) ?? "called_at",
    order: (get("order") as "asc" | "desc" | undefined) ?? "desc",
  };
}

export function CallsView() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const params = useMemo(() => parseParams(sp), [sp]);
  const [uploadOpen, setUploadOpen] = useState(sp.get("upload") === "1");
  const [search, setSearch] = useState(params.q ?? "");

  const update = (patch: Record<string, string | undefined>, keepPage = false) => {
    const next = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") next.delete(k);
      else next.set(k, v);
    }
    if (!keepPage) next.delete("page");
    next.delete("upload");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  // Debounce the search box into the URL.
  useEffect(() => {
    const trimmed = search.trim();
    if (trimmed === (params.q ?? "")) return;
    const t = setTimeout(() => update({ q: trimmed }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const key = JSON.stringify(params);
  const calls = useAsync(() => api.listCalls(params), key);
  const agents = useAsync(() => api.listAgents(), "agents");
  const rules = useAsync(() => api.listRules(), "rules");

  // Refetch every 5 s while any call on the page is still being processed.
  const pending = calls.data?.items.some((c) => !isTerminal(c.status)) ?? false;
  const { poll } = calls;
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(poll, POLL_MS);
    return () => clearInterval(t);
  }, [pending, poll]);

  const sort: SortState = { key: params.sort ?? "called_at", order: params.order ?? "desc" };
  const onSort = (k: string) =>
    update({ sort: k, order: sort.key === k && sort.order === "desc" ? "asc" : "desc" });

  const hasFilters = Boolean(params.q || params.agent_id || params.language || params.status || params.severity || params.rule_code || params.date_from || params.date_to);
  const clear = () => {
    setSearch("");
    router.replace(pathname, { scroll: false });
  };

  const total = calls.data?.total ?? 0;
  return (
    <>
      <PageHeader
        title="Calls"
        description="Every recording submitted for audit."
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload aria-hidden data-icon="inline-start" />
            Upload calls
          </Button>
        }
      />
      <PageContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2" role="search" aria-label="Filter calls">
          <div className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-2 left-2.5 size-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search call ID or loan ref"
              aria-label="Search by call ID or loan reference"
              className="h-7 w-60 pl-8"
            />
          </div>
          <FilterSelect
            label="Agent"
            allLabel="All agents"
            value={params.agent_id}
            options={(agents.data ?? []).map((a) => ({ value: a.id, label: a.name }))}
            onChange={(v) => update({ agent_id: v })}
          />
          <FilterSelect
            label="Language"
            allLabel="All languages"
            value={params.language}
            options={[
              { value: "hinglish", label: "Hinglish" },
              { value: "marathi", label: "Marathi" },
            ]}
            onChange={(v) => update({ language: v })}
          />
          <FilterSelect
            label="Status"
            allLabel="All statuses"
            value={params.status}
            options={(["queued", "transcribing", "analysing", "done", "failed"] as const).map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
            onChange={(v) => update({ status: v })}
          />
          <FilterSelect
            label="Severity"
            allLabel="Any severity"
            value={params.severity}
            options={[
              { value: "critical", label: "Critical" },
              { value: "high", label: "High" },
              { value: "medium", label: "Medium" },
            ]}
            onChange={(v) => update({ severity: v })}
          />
          <FilterSelect
            label="Rule"
            allLabel="Any rule"
            value={params.rule_code}
            options={(rules.data ?? []).map((r) => ({ value: r.code, label: `${r.code} ${r.name}` }))}
            onChange={(v) => update({ rule_code: v })}
          />
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            From
            <Input type="date" aria-label="Called from date" value={params.date_from ?? ""} onChange={(e) => update({ date_from: e.target.value })} className="tnum h-7 w-36" />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            To
            <Input type="date" aria-label="Called to date" value={params.date_to ?? ""} onChange={(e) => update({ date_to: e.target.value })} className="tnum h-7 w-36" />
          </label>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clear}>
              <X aria-hidden data-icon="inline-start" />
              Clear filters
            </Button>
          )}
        </div>

        <div className="overflow-hidden rounded-lg border">
          <DataTable
            label="Calls"
            minWidth={880}
            data={calls.data?.items ?? []}
            columns={columns}
            getRowId={(c) => c.id}
            sortKeys={SORT_KEYS}
            sort={sort}
            onSortChange={onSort}
            rowHref={(c) => `/calls/${c.id}`}
            loading={calls.loading}
            refreshing={calls.refreshing}
            error={calls.error}
            onRetry={calls.reload}
            skeletonRows={10}
            empty={
              hasFilters
                ? { title: "No calls match these filters", description: "Widen the date range or clear a filter.", action: <Button variant="outline" size="sm" onClick={clear}>Clear filters</Button> }
                : { title: "No calls yet", description: "Upload recordings to start auditing.", action: <Button size="sm" onClick={() => setUploadOpen(true)}>Upload calls</Button> }
            }
          />
          {calls.data && total > 0 && (
            <Pagination page={calls.data.page} pageSize={calls.data.page_size} total={total} onPageChange={(p) => update({ page: String(p) }, true)} />
          )}
        </div>
        {pending && <p className="text-xs text-muted-foreground">Some calls are still processing. This list refreshes every 5 seconds.</p>}
      </PageContent>

      <UploadDrawer
        open={uploadOpen}
        onOpenChange={(o) => {
          setUploadOpen(o);
          if (!o && sp.get("upload")) update({});
        }}
        agents={agents.data ?? []}
        onUploaded={() => {
          calls.reload();
          agents.reload();
        }}
      />
    </>
  );
}

