import { Check, X } from "lucide-react";

/** A static, decorative mock of the call analysis screen. The text is from one of the demo calls; nothing here is interactive. */
export function AnalysisPreview() {
  const bars = Array.from({ length: 56 }, (_, i) => 16 + Math.round(60 * Math.abs(Math.sin(i * 0.37) * Math.cos(i * 0.12 + 0.6))));
  const hit = new Set([17, 18, 36, 37]);
  return (
    <div aria-hidden className="lp-card mx-auto w-full max-w-5xl overflow-hidden rounded-2xl shadow-[0_40px_120px_-40px_rgba(53,201,176,0.35)]">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
        <span className="size-2.5 rounded-full bg-white/20" />
        <span className="size-2.5 rounded-full bg-white/20" />
        <span className="size-2.5 rounded-full bg-white/20" />
        <span className="ml-3 truncate text-xs text-white/45">Call analysis · Imran Shaikh · demo call</span>
        <span className="ml-auto rounded-full border border-[#ff5a47]/40 bg-[#ff5a47]/10 px-2.5 py-0.5 text-xs font-medium text-[#ff9b8f]">Score 40</span>
      </div>
      <div className="grid gap-0 md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-4 p-5">
          <div className="flex h-20 items-center gap-[3px] rounded-lg bg-white/[0.03] px-3">
            {bars.map((h, i) => (
              <span key={i} className="block flex-1 rounded-full" style={{ height: `${h}%`, background: hit.has(i) ? "var(--lp-coral)" : "#35c9b0", opacity: hit.has(i) ? 1 : 0.7 }} />
            ))}
          </div>
          <ul className="space-y-2 text-sm">
            {[
              ["00:10", "Agent", "नवीन जी, आपकी personal loan की 2 EMI pending है, कुल 16,000 रुपये।", false],
              ["00:26", "Agent", "मैं RBI के recovery cell से बोल रहा हूँ, आपका case हमारे पास आ चुका है।", true],
              ["00:34", "Borrower", "RBI के recovery cell से? आपने तो सहयोग finance बोला था?", false],
              ["00:51", "Agent", "कल police आ जाएगी और jail भेज देंगे, आप सोच लीजिए।", true],
            ].map(([t, who, line, flag]) => (
              <li key={String(t)} className={`flex gap-3 rounded-lg px-3 py-2 ${flag ? "bg-[#ff5a47]/10 ring-1 ring-[#ff5a47]/30" : ""}`}>
                <span className="tnum w-10 shrink-0 text-xs text-white/40">{String(t)}</span>
                <span className="w-16 shrink-0 text-xs font-medium text-white/50">{String(who)}</span>
                <span className="text-white/85">{String(line)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-3 border-t border-white/10 p-5 md:border-t-0 md:border-l">
          <p className="text-xs font-medium tracking-wide text-white/45 uppercase">Flagged moments · 2</p>
          {[
            ["V7", "Impersonation or false authority", "00:26", "“मैं RBI के recovery cell से बोल रहा हूँ”"],
            ["V4", "False legal threat", "00:51", "“कल police आ जाएगी और jail भेज देंगे”"],
          ].map(([code, name, at, quote]) => (
            <div key={code} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-white">
                  <span className="mr-2 rounded bg-[#ff5a47]/15 px-1.5 py-0.5 text-xs text-[#ff9b8f]">{code}</span>
                  {name}
                </p>
                <span className="tnum text-xs text-white/40">{at}</span>
              </div>
              <p className="mt-2 text-sm text-white/60">{quote}</p>
              <div className="mt-3 flex gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-[#35c9b0] px-3 py-1 text-xs font-medium text-[#06201c]">
                  <Check className="size-3" />
                  Confirm
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-white/15 px-3 py-1 text-xs text-white/70">
                  <X className="size-3" />
                  Dismiss
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
