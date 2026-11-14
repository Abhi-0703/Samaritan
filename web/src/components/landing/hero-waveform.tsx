import { cn } from "@/lib/utils";

const BARS = 72;
// Bars that carry a violation, with the chip that names it. Positions are fractions of the width.
const FLAGS: { bar: number; label: string; hide?: string; raise?: string }[] = [
  { bar: 14, label: "V7 · Impersonation" },
  { bar: 36, label: "V4 · False legal threat", raise: "max-sm:-translate-y-[4.6rem]" }, // staggered on phones so the chips do not overlap
  { bar: 57, label: "V1 · Call after 7 pm", hide: "hidden sm:flex" },
];
const flagged = new Set(FLAGS.flatMap((f) => [f.bar, f.bar + 1]));

function height(i: number) {
  const envelope = Math.abs(Math.sin(i * 0.31) * Math.cos(i * 0.09 + 1));
  const detail = 0.82 + 0.18 * Math.sin(i * 1.7);
  return Math.round(18 + 74 * envelope * detail);
}

/** A decorative speech waveform with three flagged moments: the signature image of the product. */
export function HeroWaveform({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("relative mx-auto w-full max-w-5xl", className)}>
      <div className="relative h-44 sm:h-56">
        <div className="lp-fade-x absolute inset-0 flex items-center gap-[3px] sm:gap-1">
          {Array.from({ length: BARS }, (_, i) => (
            <span
              key={i}
              className="lp-bar block flex-1 rounded-full"
              style={{
                height: `${flagged.has(i) ? Math.max(height(i), 78) : height(i)}%`,
                animationDelay: `${(i % 12) * 0.18}s`,
                background: flagged.has(i) ? "var(--lp-coral)" : "linear-gradient(180deg, #7be3d0, #35c9b0 55%, #1f8f7c)",
                boxShadow: flagged.has(i) ? "0 0 18px rgba(255,90,71,0.55)" : "none",
              }}
            />
          ))}
        </div>
        <div className="lp-sweep pointer-events-none absolute inset-y-0 w-px bg-white/50 shadow-[0_0_14px_rgba(255,255,255,0.7)]" />
      </div>
      {FLAGS.map((f, i) => (
        <span
          key={f.label}
          className={cn(
            "lp-float absolute top-0 flex -translate-x-1/2 -translate-y-9 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap text-[#1a0805] shadow-[0_8px_30px_-8px_rgba(255,90,71,0.9)] sm:text-sm",
            f.hide,
            f.raise,
          )}
          style={{ left: `${((f.bar + 1) / BARS) * 100}%`, background: "var(--lp-coral)", animationDelay: `${i * 0.7}s` }}
        >
          <span className="size-1.5 rounded-full bg-[#1a0805]" />
          {f.label}
        </span>
      ))}
    </div>
  );
}
