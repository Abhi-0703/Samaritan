"use client";

import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { ReviewerBadge, RuleCode, SeverityBadge } from "@/components/badges";
import { PageContent, PageHeader } from "@/components/page-header";
import { BlockSkeleton, ErrorState } from "@/components/states";
import { Button, buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatClock, formatDuration, formatLongDateTime } from "@/lib/format";
import { useAsync } from "@/lib/hooks/use-async";
import type { Violation } from "@/lib/types";

const DETECTED: Record<Violation["detected_by"], string> = {
  rules: "Keyword rules",
  llm: "Language model",
  both: "Keyword rules and language model",
  metadata: "Call metadata",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[160px_1fr] gap-3 py-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function EvidenceView({ id }: { id: string }) {
  const call = useAsync(() => api.getCall(id), id);
  const rules = useAsync(() => api.listRules(), "rules");

  const back = (
    <Link href={`/calls/${id}`} aria-label="Back to call" className={buttonVariants({ variant: "ghost", size: "icon-sm" })}>
      <ArrowLeft aria-hidden />
    </Link>
  );

  if (call.error && !call.data) {
    return (
      <>
        <PageHeader title="Evidence summary" back={back} />
        <PageContent>
          <ErrorState message={call.error.message} onRetry={call.reload} />
        </PageContent>
      </>
    );
  }
  if (!call.data) {
    return (
      <>
        <PageHeader title="Evidence summary" back={back} />
        <PageContent>
          <BlockSkeleton className="h-64" />
        </PageContent>
      </>
    );
  }

  const d = call.data;
  const findings = d.violations.filter((v) => v.reviewer_status !== "dismissed");
  const dismissed = d.violations.length - findings.length;
  const segmentFor = (v: Violation) => d.segments.find((s) => s.id === v.segment_id);
  const rbi = (code: string) => rules.data?.find((r) => r.code === code)?.rbi_reference ?? "-";

  return (
    <>
      <PageHeader
        title="Evidence summary"
        description={d.id}
        back={back}
        actions={
          <Button onClick={() => window.print()} disabled={d.status !== "done"}>
            <Printer aria-hidden data-icon="inline-start" />
            Print
          </Button>
        }
      />
      <PageContent className="max-w-[860px] space-y-8">
        <header className="border-b pb-4">
          <p className="text-xs text-muted-foreground">Samaritan call audit</p>
          <h2 className="mt-1 text-base font-semibold">Sahyog Finance, Collections QA</h2>
          <p className="text-muted-foreground">Evidence summary for call {d.id}</p>
        </header>

        <section aria-label="Call details">
          <h3 className="mb-2 font-semibold">Call details</h3>
          <dl className="divide-y rounded-lg border px-4">
            <Row label="Call ID">
              <span className="font-mono text-xs">{d.id}</span>
            </Row>
            <Row label="Loan reference">
              <span className="font-mono text-xs">{d.loan_ref}</span>
            </Row>
            <Row label="Agent">{d.agent_name}</Row>
            <Row label="Called at">{formatLongDateTime(d.called_at)}</Row>
            <Row label="Duration">{formatDuration(d.duration_s)}</Row>
            <Row label="Language">
              <span className="capitalize">{d.language}</span>
            </Row>
            <Row label="Compliance score">{d.score === null ? "-" : `${Math.round(d.score)} out of 100`}</Row>
            {d.transcription && <Row label="Transcription">Gnani Prisma ({d.transcription.model}), language {d.transcription.language_code}</Row>}
          </dl>
        </section>

        <section aria-label="Findings">
          <h3 className="mb-2 font-semibold">
            Findings <span className="tnum font-normal text-muted-foreground">({findings.length})</span>
          </h3>
          {d.status !== "done" ? (
            <p className="rounded-lg border p-4 text-muted-foreground">This call has not finished processing, so there are no findings to show yet.</p>
          ) : findings.length === 0 ? (
            <p className="rounded-lg border p-4 text-muted-foreground">No rule was broken on this call.</p>
          ) : (
            <ol className="space-y-4">
              {findings.map((v, i) => {
                const seg = segmentFor(v);
                return (
                  <li key={v.id} className="break-inside-avoid rounded-lg border p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="tnum text-muted-foreground">{i + 1}.</span>
                      <RuleCode code={v.rule_code} />
                      <span className="font-medium">{v.rule_name}</span>
                      <SeverityBadge severity={v.severity} />
                      <span className="ml-auto">
                        <ReviewerBadge status={v.reviewer_status} />
                      </span>
                    </div>
                    <dl className="mt-3 divide-y">
                      <Row label="Evidence">
                        {v.quote ? (
                          <blockquote className="border-l-2 pl-3">{`“${v.quote}”`}</blockquote>
                        ) : v.rule_code === "V1" ? (
                          "Call metadata: the call start time"
                        ) : (
                          "First 60 seconds of the call"
                        )}
                      </Row>
                      <Row label="Timestamp">
                        <span className="tnum font-mono text-xs">
                          {v.start_s !== null ? formatClock(v.start_s) : "Not applicable"}
                          {seg && `, ${seg.speaker === "agent" ? "Agent" : "Borrower"}`}
                        </span>
                      </Row>
                      <Row label="Why it was flagged">{v.explanation}</Row>
                      <Row label="RBI reference">{rbi(v.rule_code)}</Row>
                      <Row label="Detected by">
                        {DETECTED[v.detected_by]}, confidence <span className="tnum">{Math.round(v.confidence * 100)}%</span>
                      </Row>
                    </dl>
                  </li>
                );
              })}
            </ol>
          )}
          {dismissed > 0 && (
            <p className="mt-3 text-xs text-muted-foreground">
              {dismissed} flag{dismissed === 1 ? " was" : "s were"} dismissed by a reviewer and {dismissed === 1 ? "is" : "are"} not listed.
            </p>
          )}
        </section>

        <footer className="border-t pt-4 text-muted-foreground">
          Automated findings are decision support and require human review. Generated by Samaritan from a synthetic recording.
        </footer>
      </PageContent>
    </>
  );
}
