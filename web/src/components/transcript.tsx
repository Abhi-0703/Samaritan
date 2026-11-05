"use client";

import { useEffect, useMemo, useRef } from "react";
import { severityBorderClass } from "@/components/badges";
import { formatClock, severityRank } from "@/lib/format";
import type { Segment, Severity, Violation } from "@/lib/types";
import { cn } from "@/lib/utils";

const speakerLabel: Record<Segment["speaker"], string> = { agent: "Agent", borrower: "Borrower", unknown: "Speaker" };

const markBg: Record<Severity, string> = {
  critical: "bg-critical-bg",
  high: "bg-high-bg",
  medium: "bg-medium-bg",
};

function Highlighted({ text, quote, severity }: { text: string; quote: string | null; severity: Severity | null }) {
  if (!quote || !severity) return <>{text}</>;
  const i = text.indexOf(quote);
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className={cn("rounded-sm px-0.5 text-foreground", markBg[severity])}>{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  );
}

export function TranscriptView({
  segments,
  violations,
  currentTime,
  onSeek,
}: {
  segments: Segment[];
  violations: Violation[];
  currentTime: number;
  onSeek: (seconds: number) => void;
}) {
  const flagsBySegment = useMemo(() => {
    const map = new Map<string, Violation[]>();
    for (const v of violations) {
      if (!v.segment_id || v.reviewer_status === "dismissed") continue;
      map.set(v.segment_id, [...(map.get(v.segment_id) ?? []), v]);
    }
    return map;
  }, [violations]);

  const activeIndex = useMemo(() => {
    let found = -1;
    segments.forEach((s, i) => {
      if (s.start_s <= currentTime) found = i;
    });
    return found >= 0 && currentTime <= segments[found].end_s + 0.6 ? found : -1;
  }, [segments, currentTime]);

  const rows = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    if (activeIndex < 0) return;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    rows.current[activeIndex]?.scrollIntoView({ block: "nearest", behavior: calm ? "auto" : "smooth" });
  }, [activeIndex]);

  return (
    <ol className="divide-y overflow-hidden rounded-lg border" aria-label="Transcript">
      {segments.map((s, i) => {
        const flags = flagsBySegment.get(s.id) ?? [];
        const top = flags.reduce<Violation | null>((m, v) => (!m || severityRank[v.severity] > severityRank[m.severity] ? v : m), null);
        const active = i === activeIndex;
        return (
          <li key={s.id}>
            <button
              ref={(el) => {
                rows.current[i] = el;
              }}
              type="button"
              onClick={() => onSeek(s.start_s)}
              aria-current={active ? "true" : undefined}
              aria-label={`${formatClock(s.start_s)} ${speakerLabel[s.speaker]}${top ? `, flagged ${top.severity}` : ""}: ${s.text}`}
              className={cn(
                "grid w-full grid-cols-[48px_72px_1fr] items-start gap-3 border-l-2 px-4 py-2.5 text-left transition-colors duration-150 hover:bg-surface",
                top ? severityBorderClass[top.severity] : "border-l-transparent",
                active && "bg-brand-subtle hover:bg-brand-subtle",
              )}
            >
              <span className="tnum pt-0.5 font-mono text-xs text-muted-foreground">{formatClock(s.start_s)}</span>
              <span className={cn("pt-0.5 text-xs font-medium", s.speaker === "agent" ? "text-foreground" : "text-muted-foreground")}>
                {speakerLabel[s.speaker]}
              </span>
              <span lang={/[ऀ-ॿ]/.test(s.text) ? "mr" : undefined}>
                <Highlighted text={s.text} quote={top?.quote ?? null} severity={top?.severity ?? null} />
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
