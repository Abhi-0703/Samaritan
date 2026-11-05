"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDayLabel } from "@/lib/format";
import type { OverviewStats, Severity } from "@/lib/types";

function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string; swatch?: string }[] }) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 text-muted-foreground">
          {r.swatch && <span aria-hidden className={`size-2 rounded-sm ${r.swatch}`} />}
          <span>{r.label}</span>
          <span className="tnum ml-auto pl-3 font-medium text-foreground">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; swatch: string }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span aria-hidden className={`size-2 rounded-sm ${i.swatch}`} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

export function ViolationsPerDayChart({ data }: { data: OverviewStats["violations_per_day"] }) {
  const rows = data.map((d) => ({ ...d, label: formatDayLabel(d.date) }));
  return (
    <div>
      <div role="img" aria-label="Stacked bar chart of violations per day over the last 14 days, split by severity" className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="label" tickLine={false} interval={1} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={String(label)}
                    rows={[
                      { label: "Critical", value: String(payload.find((p) => p.dataKey === "critical")?.value ?? 0), swatch: "bg-critical" },
                      { label: "High", value: String(payload.find((p) => p.dataKey === "high")?.value ?? 0), swatch: "bg-high" },
                      { label: "Medium", value: String(payload.find((p) => p.dataKey === "medium")?.value ?? 0), swatch: "bg-medium" },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="critical" stackId="s" className="fill-critical stroke-background" strokeWidth={1} isAnimationActive={false} />
            <Bar dataKey="high" stackId="s" className="fill-high stroke-background" strokeWidth={1} isAnimationActive={false} />
            <Bar dataKey="medium" stackId="s" className="fill-medium stroke-background" strokeWidth={1} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend
        items={[
          { label: "Critical", swatch: "bg-critical" },
          { label: "High", swatch: "bg-high" },
          { label: "Medium", swatch: "bg-medium" },
        ]}
      />
    </div>
  );
}

const SEVERITY_FILL: Record<Severity, string> = { critical: "fill-critical", high: "fill-high", medium: "fill-medium" };

export function ViolationsByRuleChart({ data }: { data: { rule_code: string; rule_name: string; count: number; severity: Severity }[] }) {
  return (
    <div role="img" aria-label="Horizontal bar chart of violations by rule" style={{ height: Math.max(120, data.length * 36 + 24) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" allowDecimals={false} tickLine={false} />
          <YAxis type="category" dataKey="rule_code" tickLine={false} width={36} />
          <Tooltip
            isAnimationActive={false}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof data)[number] | undefined;
              return active && row ? <TooltipBox title={`${row.rule_code} ${row.rule_name}`} rows={[{ label: "Violations", value: String(row.count) }]} /> : null;
            }}
          />
          <Bar dataKey="count" barSize={16} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.rule_code} className={SEVERITY_FILL[d.severity]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ScoreTrendChart({ data }: { data: { date: string; avg_score: number; calls: number }[] }) {
  const rows = data.map((d) => ({ ...d, label: formatDayLabel(d.date), score: Math.round(d.avg_score) }));
  return (
    <div role="img" aria-label="Line chart of the average compliance score per day" className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} />
          <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
          <Tooltip
            isAnimationActive={false}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined;
              return active && row ? (
                <TooltipBox
                  title={row.label}
                  rows={[
                    { label: "Average score", value: String(row.score) },
                    { label: "Calls", value: String(row.calls) },
                  ]}
                />
              ) : null;
            }}
          />
          <Line type="monotone" dataKey="score" strokeWidth={2} className="stroke-brand" dot={{ r: 3, className: "fill-brand stroke-brand" }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GroupedMetricsChart({
  data,
}: {
  data: { metric: string; rules_only: number; rules_plus_llm: number }[];
}) {
  return (
    <div>
      <div role="img" aria-label="Grouped bar chart comparing rules only with rules plus language model on precision, recall and F1" className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={4}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="metric" tickLine={false} />
            <YAxis domain={[0, 100]} tickLine={false} axisLine={false} unit="%" />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={String(label)}
                    rows={[
                      { label: "Rules only", value: `${payload.find((p) => p.dataKey === "rules_only")?.value}%`, swatch: "bg-muted-foreground" },
                      { label: "Rules + LLM", value: `${payload.find((p) => p.dataKey === "rules_plus_llm")?.value}%`, swatch: "bg-brand" },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="rules_only" className="fill-muted-foreground" barSize={28} isAnimationActive={false} />
            <Bar dataKey="rules_plus_llm" className="fill-brand" barSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend
        items={[
          { label: "Rules only", swatch: "bg-muted-foreground" },
          { label: "Rules + LLM", swatch: "bg-brand" },
        ]}
      />
    </div>
  );
}
