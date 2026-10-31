import { cn } from "@/lib/utils";
import { formatScore, severityLabel, statusLabel } from "@/lib/format";
import type { CallStatus, DetectedBy, ReviewerStatus, Severity } from "@/lib/types";

const pill =
  "inline-flex h-5 shrink-0 items-center gap-1 rounded-full border px-2 text-xs font-medium whitespace-nowrap";

const tone = {
  critical: "border-critical/30 bg-critical-bg text-critical",
  high: "border-high/30 bg-high-bg text-high",
  medium: "border-medium/30 bg-medium-bg text-medium",
  ok: "border-ok/30 bg-ok-bg text-ok",
  brand: "border-brand/30 bg-brand-subtle text-brand-text",
  neutral: "border-border bg-surface text-muted-foreground",
} as const;

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return <span className={cn(pill, tone[severity], className)}>{severityLabel[severity]}</span>;
}

const statusTone: Record<CallStatus, string> = {
  queued: tone.neutral,
  transcribing: tone.brand,
  analysing: tone.brand,
  done: tone.ok,
  failed: tone.critical,
};

export function StatusBadge({ status, className }: { status: CallStatus; className?: string }) {
  const working = status === "transcribing" || status === "analysing";
  return (
    <span className={cn(pill, statusTone[status], className)}>
      {working && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-current" />}
      {statusLabel[status]}
    </span>
  );
}

/** 85 and above is compliant, 60 to 84 medium, below 60 critical (plan Section 3.2). */
export function ScoreBadge({ score, className }: { score: number | null; className?: string }) {
  if (score === null) return <span className="tnum text-muted-foreground">-</span>;
  const t = score >= 85 ? tone.ok : score >= 60 ? tone.medium : tone.critical;
  return <span className={cn(pill, "tnum min-w-9 justify-center", t, className)}>{formatScore(score)}</span>;
}

const detectedLabel: Record<DetectedBy, string> = {
  rules: "Rules",
  llm: "LLM",
  both: "Rules + LLM",
  metadata: "Call metadata",
};

export function DetectedByLabel({ value }: { value: DetectedBy }) {
  return <span>{detectedLabel[value]}</span>;
}

const reviewerLabel: Record<ReviewerStatus, string> = {
  open: "Open",
  confirmed: "Confirmed",
  dismissed: "Dismissed",
};

export function ReviewerBadge({ status }: { status: ReviewerStatus }) {
  const t = status === "confirmed" ? tone.critical : status === "dismissed" ? tone.neutral : tone.brand;
  return <span className={cn(pill, t)}>{reviewerLabel[status]}</span>;
}

export function RuleCode({ code, className }: { code: string; className?: string }) {
  return <span className={cn("font-mono text-xs font-medium", className)}>{code}</span>;
}

export const severityTextClass: Record<Severity, string> = {
  critical: "text-critical",
  high: "text-high",
  medium: "text-medium",
};

export const severityBorderClass: Record<Severity, string> = {
  critical: "border-l-critical",
  high: "border-l-high",
  medium: "border-l-medium",
};
