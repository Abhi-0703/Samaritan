"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, CircleAlert, FileText, Loader2, MoreHorizontal, RefreshCw, Repeat2 } from "lucide-react";
import { toast } from "sonner";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { AudioPlayer, type AudioPlayerHandle } from "@/components/audio-player";
import { PageContent, PageHeader } from "@/components/page-header";
import { usePasscodeGate } from "@/components/passcode-gate";
import { BlockSkeleton, ErrorState } from "@/components/states";
import { TranscriptView } from "@/components/transcript";
import { Button, buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ViolationsPanel } from "@/components/violations-panel";
import { api } from "@/lib/api";
import { formatDuration, formatLongDateTime, isTerminal, statusLabel } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { CallDetail, CallStatus, ReviewerStatus, Violation } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS: CallStatus[] = ["queued", "transcribing", "analysing", "done"];

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium break-words">{children}</dd>
    </div>
  );
}

function ProcessingCard({ status }: { status: CallStatus }) {
  const current = STEPS.indexOf(status);
  return (
    <div className="rounded-lg border p-6" role="status" aria-live="polite">
      <p className="font-semibold">This call is being processed</p>
      <p className="mt-1 text-muted-foreground">The transcript and flags appear here when processing finishes. This page updates by itself.</p>
      <ol className="mt-4 flex flex-wrap gap-x-8 gap-y-2">
        {STEPS.map((s, i) => (
          <li key={s} className={cn("flex items-center gap-2", i > current && "text-muted-foreground")}>
            {i < current ? (
              <Check aria-hidden className="size-4 text-ok" />
            ) : i === current ? (
              <Loader2 aria-hidden className="size-4 animate-spin text-brand" />
            ) : (
              <span aria-hidden className="size-4 rounded-full border" />
            )}
            <span className={cn(i === current && "font-medium")}>{statusLabel[s]}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function CallDetailView({ id }: { id: string }) {
  const sp = useSearchParams();
  const initialSeek = sp.get("t") !== null ? Number(sp.get("t")) : null;
  const call = useAsync(() => api.getCall(id), id);
  const status = call.data?.status;
  const audioReady = status === "analysing" || status === "done";
  const audio = useAsync(() => (audioReady ? api.getAudioUrl(id) : Promise.resolve(null)), `audio:${id}:${audioReady}`);
  const player = useRef<AudioPlayerHandle>(null);
  const [time, setTime] = useState(0);
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const { gate, dialog } = usePasscodeGate();

  const { poll } = call;
  const processing = status !== undefined && !isTerminal(status);
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(poll, 2500);
    return () => clearInterval(t);
  }, [processing, poll]);

  const markers = useMemo(
    () =>
      (call.data?.violations ?? [])
        .filter((v) => v.reviewer_status !== "dismissed" && v.start_s !== null && v.rule_code !== "V8")
        .map((v) => ({ id: v.id, time: v.start_s ?? 0, severity: v.severity })),
    [call.data?.violations],
  );

  const review = async (v: Violation, next: ReviewerStatus) => {
    setBusy((b) => new Set(b).add(v.id));
    call.setData((prev) => ({ ...prev, violations: prev.violations.map((x) => (x.id === v.id ? { ...x, reviewer_status: next } : x)) }));
    try {
      const res = await api.updateViolation(v.id, next);
      call.setData((prev) => ({
        ...prev,
        score: res.call_score,
        violations: prev.violations.map((x) => (x.id === v.id ? res.violation : x)),
      }));
      call.poll();
    } catch (e) {
      call.reload();
      toast.error(e instanceof Error ? e.message : "The review could not be saved.");
    } finally {
      setBusy((b) => {
        const n = new Set(b);
        n.delete(v.id);
        return n;
      });
    }
  };

  const swapRoles = () =>
    gate(async (passcode) => {
      const detail = await api.swapRoles(id, { passcode });
      call.setData(() => detail);
      toast.success("Roles swapped. Detection was re-run on the corrected speakers.");
    });

  const retry = (label: string) =>
    gate(async (passcode) => {
      await api.retryCall(id, { passcode });
      toast(label);
      call.reload();
    });

  const back = (
    <Link href="/calls" aria-label="Back to calls" className={buttonVariants({ variant: "ghost", size: "icon-sm" })}>
      <ArrowLeft aria-hidden />
    </Link>
  );

  if (call.error && !call.data) {
    return (
      <>
        <PageHeader title="Call" back={back} />
        <PageContent>
          <ErrorState title="Could not open this call" message={call.error.message} onRetry={call.reload} />
        </PageContent>
      </>
    );
  }

  if (!call.data) {
    return (
      <>
        <PageHeader title="Call" back={back} />
        <PageContent>
          <BlockSkeleton className="h-20" />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
            <div className="space-y-6">
              <BlockSkeleton className="h-36" />
              <BlockSkeleton className="h-96" />
            </div>
            <BlockSkeleton className="h-96" />
          </div>
        </PageContent>
      </>
    );
  }

  const d: CallDetail = call.data;
  const done = d.status === "done";

  return (
    <>
      <PageHeader
        title={d.id}
        description={`${d.agent_name}, ${formatLongDateTime(d.called_at)}`}
        back={back}
        actions={
          <>
            {done && (
              <Link href={`/calls/${d.id}/evidence`} aria-label="Evidence summary" className={buttonVariants({ variant: "outline" })}>
                <FileText aria-hidden data-icon="inline-start" />
                <span className="hidden sm:inline">Evidence summary</span>
              </Link>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" size="icon" aria-label="More actions" />}>
                <MoreHorizontal aria-hidden />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem disabled={!done} onClick={swapRoles}>
                  <Repeat2 aria-hidden />
                  Swap Agent and Borrower roles
                </DropdownMenuItem>
                <DropdownMenuItem disabled={processing} onClick={() => retry("Analysis re-run started.")}>
                  <RefreshCw aria-hidden />
                  Re-run analysis
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />
      <PageContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-lg border p-4 sm:grid-cols-4 lg:grid-cols-7">
          <Meta label="Agent">
            <Link href={`/agents/${d.agent_id}`} className="hover:underline">
              {d.agent_name}
            </Link>
          </Meta>
          <Meta label="Called at (IST)">
            <span className="tnum">{formatLongDateTime(d.called_at).replace(" IST", "")}</span>
          </Meta>
          <Meta label="Duration">
            <span className="tnum">{formatDuration(d.duration_s)}</span>
          </Meta>
          <Meta label="Language">
            <span className="capitalize">{d.language}</span>
          </Meta>
          <Meta label="Loan reference">
            <span className="font-mono text-xs">{d.loan_ref}</span>
          </Meta>
          <Meta label="Status">
            <StatusBadge status={d.status} />
          </Meta>
          <Meta label="Compliance score">
            <ScoreBadge score={d.score} />
          </Meta>
        </dl>

        {d.status === "failed" && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-critical/40 bg-critical-bg p-4">
            <div className="flex items-start gap-3">
              <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-critical" />
              <div>
                <p className="font-semibold text-critical">Processing failed</p>
                <p className="text-foreground">{d.error ?? "The call could not be processed."}</p>
              </div>
            </div>
            <Button onClick={() => retry("Retry queued. The call will be processed again.")}>
              <RefreshCw aria-hidden data-icon="inline-start" />
              Retry
            </Button>
          </div>
        )}

        {done && !d.roles_look_correct && (
          <div role="status" className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-medium/40 bg-medium-bg p-4">
            <div>
              <p className="font-semibold text-medium">Speaker roles may be swapped</p>
              <p className="text-foreground">The lines labelled Agent read like borrower speech. Swapping re-runs detection without transcribing again.</p>
            </div>
            <Button variant="outline" onClick={swapRoles}>
              <Repeat2 aria-hidden data-icon="inline-start" />
              Swap roles
            </Button>
          </div>
        )}

        {done && d.analysis_notice && (
          <div role="status" className="rounded-lg border p-4 text-muted-foreground">
            {d.analysis_notice}
          </div>
        )}

        {processing && <ProcessingCard status={d.status} />}

        {done && (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
            <div className="min-w-0 space-y-6">
              {audio.data ? (
                <AudioPlayer ref={player} url={audio.data.url} markers={markers} onTime={setTime} initialSeek={initialSeek} />
              ) : audio.error ? (
                <ErrorState title="Audio unavailable" message={audio.error.message} onRetry={audio.reload} />
              ) : (
                <BlockSkeleton className="h-36" />
              )}
              <TranscriptView
                segments={d.segments}
                violations={d.violations}
                currentTime={time}
                onSeek={(s) => player.current?.seek(s)}
              />
            </div>
            <div className="lg:sticky lg:top-[72px]">
              <ViolationsPanel violations={d.violations} busyIds={busy} onReview={(v, s) => void review(v, s)} onSeek={(s) => player.current?.seek(s, true)} />
            </div>
          </div>
        )}
      </PageContent>
      {dialog}
    </>
  );
}
