"use client";

import { Check, X } from "lucide-react";
import { DetectedByLabel, ReviewerBadge, RuleCode, SeverityBadge } from "@/components/badges";
import { EmptyState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { formatClock } from "@/lib/format";
import type { ReviewerStatus, Violation } from "@/lib/types";
import { cn } from "@/lib/utils";

function Evidence({ v, onSeek }: { v: Violation; onSeek: (s: number) => void }) {
  if (v.rule_code === "V1") {
    return <p className="text-muted-foreground">Call metadata: the call start time is the evidence.</p>;
  }
  if (v.rule_code === "V8") {
    return (
      <button type="button" onClick={() => onSeek(0)} className="text-left text-muted-foreground underline-offset-2 hover:underline">
        First 60 seconds: the introduction is missing the agent&apos;s name or the lender&apos;s name.
      </button>
    );
  }
  return (
    <div className="space-y-1.5">
      {v.quote && <blockquote className="border-l-2 border-border pl-3">{`“${v.quote}”`}</blockquote>}
      {v.start_s !== null && (
        <button
          type="button"
          onClick={() => onSeek(v.start_s ?? 0)}
          aria-label={`Play from ${formatClock(v.start_s)}`}
          className="tnum rounded-sm font-mono text-xs text-brand underline-offset-2 hover:underline"
        >
          {formatClock(v.start_s)}
        </button>
      )}
    </div>
  );
}

export function ViolationsPanel({
  violations,
  onSeek,
  onReview,
  busyIds,
}: {
  violations: Violation[];
  onSeek: (seconds: number) => void;
  onReview: (v: Violation, status: ReviewerStatus) => void;
  busyIds: Set<string>;
}) {
  const active = violations.filter((v) => v.reviewer_status !== "dismissed").length;
  return (
    <section aria-label="Flagged moments" className="rounded-lg border">
      <div className="flex h-11 items-center justify-between border-b px-4">
        <h2 className="font-semibold">Flagged moments</h2>
        <p className="tnum text-xs text-muted-foreground">
          {active} active{violations.length > active ? `, ${violations.length - active} dismissed` : ""}
        </p>
      </div>
      {violations.length === 0 ? (
        <EmptyState title="No flagged moments" description="No enabled rule was broken on this call." />
      ) : (
        <ul className="divide-y">
          {violations.map((v) => {
            const dismissed = v.reviewer_status === "dismissed";
            const busy = busyIds.has(v.id);
            return (
              <li key={v.id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <RuleCode code={v.rule_code} />
                  <span className="font-medium">{v.rule_name}</span>
                  <SeverityBadge severity={v.severity} />
                </div>
                <div className={cn("space-y-2", dismissed && "opacity-60")}>
                  <Evidence v={v} onSeek={onSeek} />
                  <p className="text-muted-foreground">{v.explanation}</p>
                  <p className="tnum text-xs text-muted-foreground">
                    Detected by <DetectedByLabel value={v.detected_by} />, confidence {Math.round(v.confidence * 100)}%
                  </p>
                </div>
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    variant={v.reviewer_status === "confirmed" ? "default" : "outline"}
                    disabled={busy}
                    aria-pressed={v.reviewer_status === "confirmed"}
                    onClick={() => onReview(v, v.reviewer_status === "confirmed" ? "open" : "confirmed")}
                  >
                    <Check aria-hidden data-icon="inline-start" />
                    Confirm
                  </Button>
                  <Button
                    size="sm"
                    variant={dismissed ? "secondary" : "outline"}
                    disabled={busy}
                    aria-pressed={dismissed}
                    onClick={() => onReview(v, dismissed ? "open" : "dismissed")}
                  >
                    <X aria-hidden data-icon="inline-start" />
                    {dismissed ? "Restore" : "Dismiss"}
                  </Button>
                  {v.reviewer_status !== "open" && (
                    <span className="ml-auto self-center">
                      <ReviewerBadge status={v.reviewer_status} />
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
