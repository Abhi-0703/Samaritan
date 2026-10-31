const parts = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** Current IST time as a datetime-local value, "2026-11-01T09:30". */
export function nowIstInput(offsetMinutes = 0): string {
  const map: Record<string, string> = {};
  for (const p of parts.formatToParts(new Date(Date.now() + offsetMinutes * 60_000))) map[p.type] = p.value;
  const hour = map.hour === "24" ? "00" : map.hour;
  return `${map.year}-${map.month}-${map.day}T${hour}:${map.minute}`;
}

/** A datetime-local value typed in IST becomes an ISO string with the +05:30 offset. */
export function istInputToIso(local: string): string {
  return `${local}:00+05:30`;
}

/** A believable default for an uploaded recording: yesterday at 11:00 IST, well inside permitted hours. */
export function defaultCallTimeInput(): string {
  return `${nowIstInput(-24 * 60).slice(0, 10)}T11:00`;
}
