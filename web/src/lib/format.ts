import type { CallStatus, Severity } from "./types";

const IST = "Asia/Kolkata";

const dateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dateFmt = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const longDateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const timeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: IST,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dayKeyFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: IST,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const numberFmt = new Intl.NumberFormat("en-IN");

/** "09 Nov, 21:40" in IST, 24-hour. */
export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso));
}

/** "09 Nov 2026, 21:40 IST" for headers and evidence pages. */
export function formatLongDateTime(iso: string): string {
  return `${longDateTimeFmt.format(new Date(iso))} IST`;
}

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

/** "21:40" in IST, 24-hour. */
export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

/** yyyy-mm-dd in IST. */
export function istDayKey(iso: string | Date): string {
  return dayKeyFmt.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** Minutes after midnight in IST, for the 08:00 to 19:00 check. */
export function istMinutes(iso: string): number {
  const [h, m] = formatTime(iso).split(":").map(Number);
  return h * 60 + m;
}

/** 134 -> "2m 14s", 45 -> "45s", null -> "-" */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) return "-";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}m ${r.toString().padStart(2, "0")}s` : `${r}s`;
}

/** 83.4 -> "01:23" for transcript timestamps. */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

export function formatNumber(n: number): string {
  return numberFmt.format(n);
}

export function formatRupees(n: number): string {
  return `₹${numberFmt.format(n)}`;
}

export function formatPct(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatScore(score: number | null): string {
  return score === null ? "-" : Math.round(score).toString();
}

export const severityLabel: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
};

export const severityRank: Record<Severity, number> = { critical: 3, high: 2, medium: 1 };

export const statusLabel: Record<CallStatus, string> = {
  queued: "Queued",
  transcribing: "Transcribing",
  analysing: "Analysing",
  done: "Done",
  failed: "Failed",
};

export function isTerminal(status: CallStatus): boolean {
  return status === "done" || status === "failed";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-31" -> "31 Oct" without any timezone conversion. */
export function formatDayLabel(key: string): string {
  const [, m, d] = key.split("-").map(Number);
  return `${d.toString().padStart(2, "0")} ${MONTHS[m - 1]}`;
}
