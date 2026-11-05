"use client";

import { useState } from "react";
import { toast } from "sonner";
import { RuleCode, SeverityBadge } from "@/components/badges";
import { createColumns, DataTable } from "@/components/data-table";
import { PageContent, PageHeader } from "@/components/page-header";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import type { Rule } from "@/lib/types";

const cols = createColumns<Rule>();

export function RulesView() {
  const { data, error, loading, reload, setData } = useAsync(() => api.listRules(), "rules");
  const [busy, setBusy] = useState<Set<string>>(new Set());

  const toggle = async (rule: Rule, enabled: boolean) => {
    setBusy((b) => new Set(b).add(rule.code));
    setData((rules) => rules.map((r) => (r.code === rule.code ? { ...r, enabled } : r)));
    try {
      await api.updateRule(rule.code, enabled);
      toast.success(
        enabled
          ? `${rule.code} enabled. Its flags are shown again and scores include it.`
          : `${rule.code} disabled. Its flags are hidden and every call and agent score was recomputed without it.`,
      );
    } catch (e) {
      setData((rules) => rules.map((r) => (r.code === rule.code ? { ...r, enabled: !enabled } : r)));
      toast.error(e instanceof Error ? e.message : "The rule could not be updated.");
    } finally {
      setBusy((b) => {
        const n = new Set(b);
        n.delete(rule.code);
        return n;
      });
    }
  };

  const columns = cols.columns([
    cols.display({ id: "code", header: "Code", cell: ({ row }) => <RuleCode code={row.original.code} /> }),
    cols.display({ id: "name", header: "Rule", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> }),
    cols.display({ id: "description", header: "What it flags", cell: ({ row }) => <span className="block max-w-[360px] py-2 text-muted-foreground">{row.original.description}</span> }),
    cols.display({ id: "rbi", header: "RBI reference", cell: ({ row }) => <span className="block max-w-[260px] py-2 text-xs text-muted-foreground">{row.original.rbi_reference}</span> }),
    cols.display({ id: "severity", header: "Severity", cell: ({ row }) => <SeverityBadge severity={row.original.severity} /> }),
    cols.display({ id: "detection", header: "Detected by", cell: ({ row }) => <span className="whitespace-nowrap">{row.original.detection}</span> }),
    cols.display({
      id: "enabled",
      header: "Enabled",
      cell: ({ row }) => (
        <Switch
          aria-label={`${row.original.enabled ? "Disable" : "Enable"} rule ${row.original.code}`}
          checked={row.original.enabled}
          disabled={busy.has(row.original.code)}
          onCheckedChange={(c) => void toggle(row.original, c === true)}
        />
      ),
    }),
  ]);

  return (
    <>
      <PageHeader title="Rules" description="The nine recovery-conduct rules every call is checked against." />
      <PageContent>
        <p className="max-w-[68ch] text-muted-foreground">
          Disabling a rule skips it in future analysis, hides its existing flags and recomputes every call and agent score without it. Existing flags are not deleted, and
          turning the rule back on restores them.
        </p>
        <div className="overflow-hidden rounded-lg border">
          <DataTable
            label="Rules"
            minWidth={1040}
            data={data ?? []}
            columns={columns}
            getRowId={(r) => r.code}
            loading={loading}
            error={error}
            onRetry={reload}
            skeletonRows={9}
            empty={{ title: "No rules configured" }}
          />
        </div>
      </PageContent>
    </>
  );
}
