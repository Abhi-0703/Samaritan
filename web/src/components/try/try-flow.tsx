"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CircleAlert, FileAudio, LayoutDashboard, Loader2, RotateCcw, UploadCloud, X } from "lucide-react";
import { ApiStatus } from "@/components/api-status";
import { CallDetailView } from "@/components/call-detail-view";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, MOCK_PASSCODE_HINT } from "@/lib/api";
import { validateAudioFile } from "@/lib/audio-file";
import { formatDuration, isTerminal, statusLabel } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import { defaultCallTimeInput, istInputToIso } from "@/lib/ist";
import { clearStoredPasscode, getStoredPasscode, setStoredPasscode } from "@/lib/passcode";
import { ApiError, type CallStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const pill = "inline-flex h-12 items-center justify-center gap-2 rounded-full px-6 text-base font-medium whitespace-nowrap transition-all duration-200";
const primary = cn(pill, "bg-[#35c9b0] text-[#06201c] shadow-[0_12px_44px_-12px_rgba(53,201,176,0.75)] hover:-translate-y-0.5 hover:bg-[#5fe0c8] disabled:pointer-events-none disabled:opacity-50");
const secondary = cn(pill, "border border-white/15 bg-white/5 text-white hover:border-white/30 hover:bg-white/10");

const STEPS: CallStatus[] = ["queued", "transcribing", "analysing", "done"];
const STEP_HINT: Record<string, string> = {
  queued: "Waiting for its turn",
  transcribing: "Gnani is turning the audio into text",
  analysing: "Checking the nine rules",
  done: "Finished",
};

function TopBar({ here }: { here: string }) {
  return (
    <header className="border-b border-white/[0.06]">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight" aria-label="Samaritan home">
          <span aria-hidden className="flex h-6 items-end gap-[2px]">
            {[10, 18, 24, 14, 20, 8].map((h, i) => (
              <span key={i} className="w-[3px] rounded-full" style={{ height: h, background: i === 2 ? "var(--lp-coral)" : "#35c9b0" }} />
            ))}
          </span>
          Samaritan
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <span className="hidden text-white/45 sm:inline">{here}</span>
          <Link href="/dashboard" className="inline-flex h-9 items-center gap-1.5 rounded-full border border-white/15 px-4 text-white/80 transition-colors hover:bg-white/10 hover:text-white">
            <LayoutDashboard aria-hidden className="size-4" />
            Dashboard
          </Link>
        </div>
      </div>
    </header>
  );
}

function Listening({ status, startedAt }: { status: CallStatus; startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(t);
  }, [startedAt]);
  const current = STEPS.indexOf(status);
  const slow = elapsed >= 120;
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-16 text-center" role="status" aria-live="polite">
      <div aria-hidden className="mx-auto flex h-24 max-w-sm items-center gap-[4px]">
        {Array.from({ length: 36 }, (_, i) => (
          <span
            key={i}
            className="lp-bar block flex-1 rounded-full bg-[#35c9b0]"
            style={{ height: `${20 + Math.round(70 * Math.abs(Math.sin(i * 0.42) * Math.cos(i * 0.13 + 1)))}%`, animationDelay: `${(i % 9) * 0.16}s` }}
          />
        ))}
      </div>
      <h1 className="mt-8 text-[clamp(1.8rem,4vw,2.6rem)] leading-tight font-semibold tracking-tight">Samaritan is listening…</h1>
      <p className="mt-2 text-base text-white/60">This page updates by itself. A short call usually takes about a minute.</p>
      <ol className="lp-card mx-auto mt-8 max-w-md space-y-1 rounded-2xl p-3 text-left">
        {STEPS.map((s, i) => (
          <li key={s} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5", i === current && "bg-white/[0.05]", i > current && "text-white/40")}>
            {i < current ? (
              <Check aria-hidden className="size-5 text-[#35c9b0]" />
            ) : i === current ? (
              <Loader2 aria-hidden className="size-5 animate-spin text-[#35c9b0]" />
            ) : (
              <span aria-hidden className="size-5 rounded-full border border-white/20" />
            )}
            <span className={cn("text-base", i === current && "font-medium")}>{statusLabel[s]}</span>
            <span className="ml-auto text-sm text-white/40">{STEP_HINT[s]}</span>
          </li>
        ))}
      </ol>
      <p className="tnum mt-6 text-sm text-white/40">{formatDuration(elapsed)} elapsed</p>
      {slow && (
        <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-white/60">
          This is taking longer than usual. The speech service can be busy at times. You can leave this page: the call will still appear in the{" "}
          <Link href="/calls" className="text-[#7be3d0] underline-offset-4 hover:underline">
            Calls list
          </Link>{" "}
          when it finishes.
        </p>
      )}
    </div>
  );
}

function Result({ id, onAnother }: { id: string; onAnother: () => void }) {
  const call = useAsync(() => api.getCall(id), `try:${id}`);
  const { poll } = call;
  const status = call.data?.status;
  const processing = status === undefined || !isTerminal(status);
  const [startedAt] = useState(() => Date.now());

  useEffect(() => {
    if (!processing) return;
    const t = setInterval(poll, 2500);
    return () => clearInterval(t);
  }, [processing, poll]);

  if (call.error && !call.data) {
    return (
      <div className="mx-auto max-w-xl px-5 py-20 text-center">
        <CircleAlert aria-hidden className="mx-auto size-8 text-[#ff9b8f]" />
        <h1 className="mt-4 text-2xl font-semibold">We lost track of this call</h1>
        <p className="mt-2 text-base text-white/60">{call.error.message}</p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button type="button" className={primary} onClick={call.reload}>
            Try again
          </button>
          <Link href="/calls" className={secondary}>
            Open the Calls list
          </Link>
        </div>
      </div>
    );
  }

  if (processing) return <Listening status={status ?? "queued"} startedAt={startedAt} />;

  const d = call.data!;
  if (d.status === "failed") {
    return (
      <div className="mx-auto max-w-xl px-5 py-20 text-center" role="alert">
        <CircleAlert aria-hidden className="mx-auto size-8 text-[#ff9b8f]" />
        <h1 className="mt-4 text-2xl font-semibold">This call could not be processed</h1>
        <p className="mt-2 text-base text-white/60">{d.error ?? "Something went wrong while transcribing it."}</p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button type="button" className={primary} onClick={onAnother}>
            <RotateCcw aria-hidden className="size-4" />
            Start over
          </button>
          <Link href={`/calls/${d.id}`} className={secondary}>
            Open the call
          </Link>
        </div>
      </div>
    );
  }

  const flags = d.violations_count;
  return (
    <>
      <div className="mx-auto w-full max-w-[1280px] px-4 pt-6 sm:px-8">
        <div className="lp-card flex flex-wrap items-center justify-between gap-4 rounded-2xl p-5">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full bg-[#35c9b0]/15 text-[#35c9b0]">
              <Check aria-hidden className="size-5" />
            </span>
            <div>
              <p className="text-lg font-semibold">Analysis ready</p>
              <p className="text-base text-white/60">
                {flags === 0 ? "No violations found" : `${flags} flagged ${flags === 1 ? "moment" : "moments"}`}
                {d.score !== null && <> · compliance score {d.score}</>}. Click a flag to hear it.
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/dashboard" className={primary}>
              <LayoutDashboard aria-hidden className="size-5" />
              Go to dashboard
              <ArrowRight aria-hidden className="size-4" />
            </Link>
            <button type="button" className={secondary} onClick={onAnother}>
              <UploadCloud aria-hidden className="size-5" />
              Analyse another call
            </button>
          </div>
        </div>
      </div>
      <div className="[&_header]:top-0">
        <CallDetailView
          id={id}
          backHref="/"
          backLabel="Back to home"
          extraActions={
            <Link href="/dashboard" className="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium hover:bg-accent">
              <LayoutDashboard aria-hidden className="size-4" />
              <span className="hidden sm:inline">Dashboard</span>
            </Link>
          }
        />
      </div>
    </>
  );
}

function UploadForm({ onUploaded }: { onUploaded: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string>();
  const [dragging, setDragging] = useState(false);
  const [agentName, setAgentName] = useState("Visitor Agent");
  const [calledAt, setCalledAt] = useState(defaultCallTimeInput);
  const [requested, setRequested] = useState(false);
  const [passcode, setPasscode] = useState(getStoredPasscode);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [formError, setFormError] = useState<string>();
  const input = useRef<HTMLInputElement>(null);

  const pick = useCallback((f: File | undefined) => {
    if (!f) return;
    setFile(f);
    setFileError(validateAudioFile(f));
    setFormError(undefined);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(undefined);
    if (!file) return setFormError("Choose an audio file first.");
    if (fileError) return;
    if (!agentName.trim()) return setFormError("Give the agent a name, any name works.");
    if (!calledAt) return setFormError("Enter when the call was made.");
    if (api.demoMode && !passcode.trim()) return setFormError("Enter the demo password to upload.");
    setBusy(true);
    try {
      const [call] = await api.uploadCalls(
        [file],
        [
          {
            filename: file.name,
            agent_name: agentName.trim(),
            called_at: istInputToIso(calledAt),
            language: "hinglish",
            loan_ref: `SF-PL-${Math.floor(100000 + Math.random() * 900000)}`,
            borrower_requested_time: requested,
          },
        ],
        { passcode: passcode.trim() || undefined, onProgress: (_i, f) => setProgress(f) },
      );
      setStoredPasscode(passcode.trim());
      onUploaded(call.id);
    } catch (err) {
      if (err instanceof ApiError && err.code === "forbidden") {
        clearStoredPasscode();
        setFormError("That password is not right. Check it and try again.");
      } else {
        setFormError(err instanceof Error ? err.message : "The upload failed. Try again.");
      }
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-12 sm:py-16">
      <p className="text-sm font-medium tracking-wide text-[#7be3d0] uppercase">Analyse a call</p>
      <h1 className="mt-3 text-[clamp(2rem,5vw,3.2rem)] leading-[1.05] font-semibold tracking-[-0.03em] text-balance">Upload a call. Watch it get audited.</h1>
      <p className="mt-4 text-base leading-relaxed text-white/60">
        Hinglish works best (English is accepted too, but less tested). Marathi is next. wav, mp3, m4a, ogg or flac, up to 25 MB.
      </p>

      <form onSubmit={submit} className="lp-card mt-8 space-y-6 rounded-3xl p-6 sm:p-8" noValidate>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files[0]);
          }}
          className={cn(
            "flex flex-col items-center gap-3 rounded-2xl border border-dashed px-4 py-10 text-center transition-colors duration-150",
            dragging ? "border-[#35c9b0] bg-[#35c9b0]/10" : "border-white/20 bg-white/[0.02]",
            fileError && "border-[#ff5a47]/60",
          )}
        >
          {file ? (
            <div className="flex w-full max-w-sm items-center gap-3 rounded-xl bg-white/[0.05] px-4 py-3 text-left">
              <FileAudio aria-hidden className="size-5 shrink-0 text-[#35c9b0]" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-medium">{file.name}</p>
                <p className="tnum text-sm text-white/45">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
              </div>
              <button type="button" aria-label="Remove file" disabled={busy} className="rounded-md p-1 text-white/50 hover:bg-white/10 hover:text-white" onClick={() => { setFile(null); setFileError(undefined); }}>
                <X aria-hidden className="size-4" />
              </button>
            </div>
          ) : (
            <>
              <span className="flex size-12 items-center justify-center rounded-2xl bg-[#35c9b0]/12 text-[#35c9b0]">
                <UploadCloud aria-hidden className="size-6" />
              </span>
              <p className="text-base font-medium">Drop an audio file here</p>
              <button type="button" className="rounded-full border border-white/20 px-4 py-2 text-sm text-white/85 hover:bg-white/10" onClick={() => input.current?.click()}>
                Choose a file
              </button>
            </>
          )}
          <input ref={input} type="file" accept=".wav,.mp3,.m4a,.ogg,.flac,audio/*" className="sr-only" aria-label="Audio file" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
          {fileError && (
            <p role="alert" className="text-sm text-[#ff9b8f]">
              {fileError}
            </p>
          )}
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="agent">Agent name</Label>
            <Input id="agent" value={agentName} onChange={(e) => setAgentName(e.target.value)} className="h-10" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="at">Call made at (IST)</Label>
            <Input id="at" type="datetime-local" value={calledAt} onChange={(e) => setCalledAt(e.target.value)} className="tnum h-10" />
          </div>
        </div>
        <p className="-mt-2 text-sm text-white/45">
          The time matters: calls before 8 am or after 7 pm break the calling-hours rule. Try 9:40 pm to see it fire.
        </p>
        <label className="flex items-center gap-3 text-base">
          <Checkbox checked={requested} onCheckedChange={(c) => setRequested(c === true)} />
          <span>The borrower asked for this call time</span>
        </label>

        {api.demoMode && (
          <div className="space-y-1.5">
            <Label htmlFor="passcode">Demo password</Label>
            <Input id="passcode" type="password" autoComplete="off" value={passcode} onChange={(e) => setPasscode(e.target.value)} className="h-10 max-w-xs" />
            <p className="text-sm text-white/45">
              Uploads use transcription credits, so they need the password from the launch post.
              {api.isMock && <> This build runs on mock data; the password is <span className="font-mono">{MOCK_PASSCODE_HINT}</span>.</>} No password? You can still{" "}
              <Link href="/dashboard" className="text-[#7be3d0] underline-offset-4 hover:underline">
                explore the analysed calls
              </Link>
              .
            </p>
          </div>
        )}

        {busy && (
          <div className="h-1.5 overflow-hidden rounded-full bg-white/10" role="progressbar" aria-label="Upload progress" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-[#35c9b0] transition-[width] duration-150" style={{ width: `${progress * 100}%` }} />
          </div>
        )}
        {formError && (
          <p role="alert" className="rounded-xl border border-[#ff5a47]/30 bg-[#ff5a47]/10 px-4 py-3 text-base text-[#ffb3a8]">
            {formError}
          </p>
        )}

        <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="inline-flex items-center justify-center gap-1.5 text-sm text-white/55 hover:text-white">
            <ArrowLeft aria-hidden className="size-4" />
            Back to home
          </Link>
          <button type="submit" className={primary} disabled={busy || !file}>
            {busy ? (
              <>
                <Loader2 aria-hidden className="size-5 animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                Analyse this call
                <ArrowRight aria-hidden className="size-4" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export function TryFlow() {
  const [callId, setCallId] = useState<string | null>(null);
  return (
    <div className="dark lp-theme min-h-screen">
      <TopBar here={callId ? "Your analysis" : "Analyse a call"} />
      <ApiStatus />
      <main>{callId ? <Result id={callId} onAnother={() => setCallId(null)} /> : <UploadForm onUploaded={setCallId} />}</main>
    </div>
  );
}
