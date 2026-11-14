"use client";

import Link from "next/link";
import { useEffect } from "react";
import { ArrowRight, AudioLines, Flag, LayoutDashboard, Quote, Scale, UploadCloud } from "lucide-react";
import { AnalysisPreview } from "@/components/landing/analysis-preview";
import { HeroWaveform } from "@/components/landing/hero-waveform";
import { api } from "@/lib/api";
import { formatPct } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import { cn } from "@/lib/utils";

const GITHUB = "https://github.com/Abhi-0703/Samaritan";

const pill = "inline-flex h-12 items-center justify-center gap-2 rounded-full px-6 text-base font-medium whitespace-nowrap transition-all duration-200";
const primaryCta = cn(
  pill,
  "bg-[#35c9b0] text-[#06201c] shadow-[0_0_0_1px_rgba(255,255,255,0.12),0_12px_44px_-10px_rgba(53,201,176,0.75)] hover:-translate-y-0.5 hover:bg-[#5fe0c8]",
);
const secondaryCta = cn(pill, "border border-white/15 bg-white/5 text-white backdrop-blur hover:-translate-y-0.5 hover:border-white/30 hover:bg-white/10");

const STEPS = [
  { icon: UploadCloud, title: "Upload a call", body: "Drop in a recording, Hinglish or English. wav, mp3, m4a, ogg or flac, up to 25 MB." },
  { icon: AudioLines, title: "It listens", body: "Gnani's Vachana speech-to-text writes the call down and tells the agent from the borrower." },
  { icon: Scale, title: "It judges", body: "Word lists and a clock check find suspects. An LLM reads the context and decides what is a real violation." },
  { icon: Flag, title: "You review", body: "Every flag sits on the waveform. Click one, hear the exact moment, then confirm or dismiss it." },
] as const;

const RULES: { code: string; name: string; severity: "Critical" | "High" | "Medium" }[] = [
  { code: "V1", name: "Call outside permitted hours", severity: "High" },
  { code: "V2", name: "Abusive or insulting language", severity: "Critical" },
  { code: "V3", name: "Threat of physical harm or force", severity: "Critical" },
  { code: "V4", name: "False legal threat", severity: "Critical" },
  { code: "V5", name: "Public shaming or threat to inform others", severity: "High" },
  { code: "V6", name: "Debt disclosed to a third party", severity: "High" },
  { code: "V7", name: "Impersonation or false authority", severity: "Critical" },
  { code: "V8", name: "No self or lender identification", severity: "Medium" },
  { code: "V9", name: "Undue pressure or intimidation", severity: "Medium" },
];
const SEVERITY_STYLE = {
  Critical: "bg-[#ff5a47]/12 text-[#ff9b8f] ring-[#ff5a47]/25",
  High: "bg-[#f59e42]/12 text-[#ffc07a] ring-[#f59e42]/25",
  Medium: "bg-[#eab308]/12 text-[#f5d56a] ring-[#eab308]/25",
} as const;

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight" aria-label="Samaritan home">
      <span aria-hidden className="flex h-6 items-end gap-[2px]">
        {[10, 18, 24, 14, 20, 8].map((h, i) => (
          <span key={i} className="w-[3px] rounded-full" style={{ height: h, background: i === 2 ? "var(--lp-coral)" : "#35c9b0" }} />
        ))}
      </span>
      <span className="text-base">Samaritan</span>
    </Link>
  );
}

function Nav() {
  const link = "text-sm text-white/60 transition-colors hover:text-white";
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#0b0f14]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-5">
        <Logo />
        <nav aria-label="Sections" className="hidden items-center gap-8 md:flex">
          <a href="#how" className={link}>
            How it works
          </a>
          <a href="#trust" className={link}>
            Why you can trust it
          </a>
          <a href="#rules" className={link}>
            The rules
          </a>
          <a href="#results" className={link}>
            Results
          </a>
          <a href={GITHUB} target="_blank" rel="noreferrer" className={link}>
            GitHub
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/dashboard" className="hidden h-9 items-center rounded-full px-4 text-sm text-white/70 transition-colors hover:text-white sm:inline-flex">
            Dashboard
          </Link>
          <Link href="/try" className="inline-flex h-9 items-center rounded-full bg-white px-4 text-sm font-medium text-[#0b0f14] transition-colors hover:bg-white/90">
            Try it
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative isolate overflow-hidden">
      <div aria-hidden className="lp-glow absolute inset-0 -z-10" />
      <div aria-hidden className="lp-grid absolute inset-0 -z-10" />
      <div className="mx-auto w-full max-w-6xl px-5 pt-16 pb-14 text-center sm:pt-24">
        <p className="lp-rise mx-auto inline-flex items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 text-sm text-white/75">
          <span aria-hidden className="lp-dot size-2 rounded-full bg-[#35c9b0]" />
          AI call auditing for lenders · built on Gnani speech-to-text
        </p>
        <h1
          className="lp-rise mx-auto mt-7 max-w-4xl text-[clamp(2.6rem,7.4vw,5.6rem)] leading-[1.02] font-semibold tracking-[-0.035em] text-balance"
          style={{ animationDelay: "0.08s" }}
        >
          Every recovery call,{" "}
          <span className="bg-gradient-to-r from-[#9ef0e0] via-[#35c9b0] to-[#7be3d0] bg-clip-text text-transparent">listened to.</span>
        </h1>
        <p className="lp-rise mx-auto mt-6 max-w-2xl text-[clamp(1.05rem,2vw,1.3rem)] leading-relaxed text-white/65 text-balance" style={{ animationDelay: "0.16s" }}>
          Samaritan audits loan-recovery calls against RBI-style conduct rules and pins every violation on the waveform. Click a flag, hear the exact moment.
        </p>
        <div className="lp-rise mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row" style={{ animationDelay: "0.24s" }}>
          <Link href="/try" className={primaryCta}>
            <UploadCloud aria-hidden className="size-5" />
            Analyse your own call
            <ArrowRight aria-hidden className="size-4" />
          </Link>
          <Link href="/dashboard" className={secondaryCta}>
            <LayoutDashboard aria-hidden className="size-5" />
            See the calls Samaritan analysed
          </Link>
        </div>
        <p className="lp-rise mt-4 text-sm text-white/45" style={{ animationDelay: "0.3s" }}>
          Browsing needs no sign-up · uploading needs the demo password
        </p>
        <div className="lp-rise mt-20 sm:mt-24" style={{ animationDelay: "0.4s" }}>
          <HeroWaveform />
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <div className="lp-card rounded-2xl p-6">
      <p className="tnum text-[clamp(2rem,4vw,2.8rem)] leading-none font-semibold tracking-tight">{value}</p>
      <p className="mt-3 text-base text-white/80">{label}</p>
      {note && <p className="mt-1 text-sm text-white/40">{note}</p>}
    </div>
  );
}

function Results() {
  const evaluation = useAsync(() => api.getLatestEval(), "landing-eval");
  const overview = useAsync(() => api.getOverview(), "landing-overview");
  const run = evaluation.data?.rules_plus_llm;
  const held = run?.per_slice.test;
  const loading = (evaluation.loading || overview.loading) && !run;
  return (
    <section id="results" className="mx-auto w-full max-w-6xl scroll-mt-24 px-5 py-20">
      <h2 className="max-w-2xl text-[clamp(1.8rem,4vw,2.8rem)] leading-tight font-semibold tracking-tight text-balance">Measured, not claimed.</h2>
      <p className="mt-3 max-w-2xl text-base text-white/60">
        Numbers come straight from the latest evaluation run, on calls recorded from scripts and labelled by hand.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }, (_, i) => <div key={i} className="lp-card h-36 animate-pulse rounded-2xl" />)
        ) : run && held ? (
          <>
            <Stat value={formatPct(held.precision, 0)} label="precision" note={`held-out calls (${held.n_calls})`} />
            <Stat value={formatPct(held.recall, 0)} label="recall" note={`held-out calls (${held.n_calls})`} />
            <Stat value={`${run.clean_calls_flagged} of ${run.clean_calls_total}`} label="clean calls wrongly flagged" />
            <Stat value={String(overview.data?.calls_audited ?? run.n_calls)} label="calls analysed so far" note="open any of them, no sign-up" />
          </>
        ) : (
          <p className="text-white/50 sm:col-span-2 lg:col-span-4">The latest results could not be loaded right now. The Accuracy page in the dashboard has them.</p>
        )}
      </div>
      <p className="mt-5 max-w-3xl text-sm leading-relaxed text-white/45">
        Honest caveats: a small set of acted Hinglish calls, with a computer-voice borrower on most of them. This is a prototype, not a legal tool.{" "}
        <Link href="/accuracy" className="text-[#7be3d0] underline-offset-4 hover:underline">
          See every number
        </Link>
        .
      </p>
    </section>
  );
}

function HowItWorks() {
  return (
    <section id="how" className="mx-auto w-full max-w-6xl scroll-mt-24 px-5 py-20">
      <p className="text-sm font-medium tracking-wide text-[#7be3d0] uppercase">How it works</p>
      <h2 className="mt-3 max-w-2xl text-[clamp(1.8rem,4vw,2.8rem)] leading-tight font-semibold tracking-tight text-balance">From a raw recording to a reviewed verdict.</h2>
      <ol className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(({ icon: Icon, title, body }, i) => (
          <li key={title} className="lp-card relative rounded-2xl p-6">
            <span className="tnum absolute top-5 right-5 text-sm text-white/25">0{i + 1}</span>
            <span className="flex size-11 items-center justify-center rounded-xl bg-[#35c9b0]/12 text-[#7be3d0] ring-1 ring-[#35c9b0]/25">
              <Icon aria-hidden className="size-5" />
            </span>
            <h3 className="mt-5 text-lg font-semibold">{title}</h3>
            <p className="mt-2 text-base leading-relaxed text-white/60">{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Trust() {
  return (
    <section id="trust" className="mx-auto w-full max-w-6xl scroll-mt-24 px-5 py-20">
      <div className="lp-card grid items-center gap-10 overflow-hidden rounded-3xl p-8 sm:p-12 lg:grid-cols-2">
        <div>
          <span className="flex size-11 items-center justify-center rounded-xl bg-[#ff5a47]/12 text-[#ff9b8f] ring-1 ring-[#ff5a47]/25">
            <Quote aria-hidden className="size-5" />
          </span>
          <h2 className="mt-5 text-[clamp(1.8rem,4vw,2.8rem)] leading-tight font-semibold tracking-tight text-balance">No quote, no flag.</h2>
          <p className="mt-4 text-base leading-relaxed text-white/65">
            The model that judges each call is not allowed to make things up. Every flag has to quote the transcript word for word. If the quote is not really in the call,
            the flag is thrown away. It cannot invent a crime.
          </p>
        </div>
        <div className="space-y-3" aria-label="Two examples">
          <div className="rounded-2xl border border-[#ff5a47]/30 bg-[#ff5a47]/[0.07] p-5">
            <p className="text-xs font-medium tracking-wide text-[#ff9b8f] uppercase">Flagged · V3 threat</p>
            <p className="mt-2 text-lg text-white/90">“Kal tak nahi bhara toh recovery wale ghar aayenge.”</p>
          </div>
          <div className="rounded-2xl border border-[#35c9b0]/30 bg-[#35c9b0]/[0.07] p-5">
            <p className="text-xs font-medium tracking-wide text-[#7be3d0] uppercase">Left alone</p>
            <p className="mt-2 text-lg text-white/90">“Helpline pe bata dijiye.”</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Rules() {
  return (
    <section id="rules" className="mx-auto w-full max-w-6xl scroll-mt-24 px-5 py-20">
      <p className="text-sm font-medium tracking-wide text-[#7be3d0] uppercase">Nine rules</p>
      <h2 className="mt-3 max-w-2xl text-[clamp(1.8rem,4vw,2.8rem)] leading-tight font-semibold tracking-tight text-balance">What Samaritan listens for.</h2>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {RULES.map((r) => (
          <li key={r.code} className="lp-card flex items-start gap-4 rounded-2xl p-5">
            <span className="tnum flex size-10 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-sm font-semibold text-white/80">{r.code}</span>
            <div className="min-w-0">
              <p className="text-base leading-snug font-medium">{r.name}</p>
              <span className={cn("mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ring-1", SEVERITY_STYLE[r.severity])}>{r.severity}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="mx-auto w-full max-w-6xl px-5 py-20">
      <div className="relative isolate overflow-hidden rounded-3xl border border-white/10 px-6 py-16 text-center sm:px-12">
        <div aria-hidden className="lp-glow absolute inset-0 -z-10" />
        <h2 className="mx-auto max-w-3xl text-[clamp(2rem,5vw,3.6rem)] leading-[1.05] font-semibold tracking-[-0.03em] text-balance">Hear what your agents really say.</h2>
        <p className="mx-auto mt-4 max-w-xl text-base text-white/60">Upload a call and watch it get audited, or open the calls Samaritan has already analysed.</p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/try" className={primaryCta}>
            <UploadCloud aria-hidden className="size-5" />
            Analyse your own call
            <ArrowRight aria-hidden className="size-4" />
          </Link>
          <Link href="/dashboard" className={secondaryCta}>
            <LayoutDashboard aria-hidden className="size-5" />
            See the analysed calls
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-5 py-10 text-sm text-white/45 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <Logo />
          <p className="pt-1">A prototype built for the Great Indian Internship Challenge, on Gnani speech-to-text. Not a legal tool.</p>
        </div>
        <div className="flex items-center gap-6">
          <a href={GITHUB} target="_blank" rel="noreferrer" className="hover:text-white">
            GitHub
          </a>
          <Link href="/dashboard" className="hover:text-white">
            Dashboard
          </Link>
          <Link href="/try" className="hover:text-white">
            Try it
          </Link>
        </div>
      </div>
    </footer>
  );
}

export function LandingPage() {
  // The free API server sleeps when idle and takes about a minute to wake. Poking it now means it is usually awake by the time a visitor clicks.
  useEffect(() => {
    api.health().catch(() => undefined);
  }, []);

  return (
    <div className="dark lp-theme min-h-screen">
      <Nav />
      <main>
        <Hero />
        <section aria-label="A preview of the call analysis screen" className="mx-auto w-full max-w-6xl px-5 pb-8">
          <AnalysisPreview />
          <p className="mt-3 text-center text-sm text-white/35">An illustration based on a demo call.</p>
        </section>
        <Results />
        <HowItWorks />
        <Trust />
        <Rules />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
