"use client";

import { useRef, useState } from "react";
import { FileAudio, FileSpreadsheet, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { FilterSelect } from "@/components/filter-select";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, MOCK_PASSCODE_HINT } from "@/lib/api";
import { defaultCallTimeInput, istInputToIso } from "@/lib/ist";
import { clearStoredPasscode, getStoredPasscode, setStoredPasscode } from "@/lib/passcode";
import { ApiError, type Agent, type Language, type UploadMetadata } from "@/lib/types";
import { cn } from "@/lib/utils";

const ALLOWED = ["wav", "mp3", "m4a", "ogg", "flac"];
const MAX_BYTES = 25 * 1024 * 1024;
const NEW_AGENT = "__new__";

interface Entry {
  key: string;
  file: File;
  agent: string; // agent id, NEW_AGENT or ""
  newAgentName: string;
  calledAt: string; // datetime-local value, interpreted as IST
  language: Language;
  loanRef: string;
  requested: boolean;
  error?: string;
}

const randomLoanRef = () => `SF-PL-${Math.floor(100000 + Math.random() * 900000)}`;

function validateFile(file: File): string | undefined {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED.includes(ext)) return "Not a supported audio file. Use wav, mp3, m4a, ogg or flac.";
  if (file.size > MAX_BYTES) return "Larger than 25 MB.";
  return undefined;
}

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [];
  const split = (line: string) => line.split(",").map((c) => c.trim().replace(/^"|"$/g, ""));
  const header = split(lines[0]).map((h) => h.toLowerCase());
  return lines.slice(1).map((l) => Object.fromEntries(split(l).map((v, i) => [header[i], v])));
}

export function UploadDrawer({
  open,
  onOpenChange,
  agents,
  onUploaded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agents: Agent[];
  onUploaded: () => void;
}) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [formError, setFormError] = useState<string>();
  const [passcode, setPasscode] = useState(getStoredPasscode);
  const fileInput = useRef<HTMLInputElement>(null);
  const csvInput = useRef<HTMLInputElement>(null);

  const addFiles = (list: FileList | File[]) => {
    const next: Entry[] = Array.from(list).map((file, i) => ({
      key: `${file.name}-${file.size}-${Date.now()}-${i}`,
      file,
      agent: "",
      newAgentName: "",
      calledAt: defaultCallTimeInput(),
      language: "hinglish",
      loanRef: randomLoanRef(),
      requested: false,
      error: validateFile(file),
    }));
    setEntries((prev) => [...prev, ...next]);
    setFormError(undefined);
  };

  const patch = (key: string, change: Partial<Entry>) =>
    setEntries((prev) => prev.map((e) => (e.key === key ? { ...e, ...change } : e)));

  const applyCsv = async (file: File) => {
    const rows = parseCsv(await file.text());
    if (rows.length === 0) {
      setFormError("The CSV needs a header row and at least one data row.");
      return;
    }
    let matched = 0;
    setEntries((prev) =>
      prev.map((e) => {
        const row = rows.find((r) => r.filename?.toLowerCase() === e.file.name.toLowerCase());
        if (!row) return e;
        matched += 1;
        const agentName = row.agent_name?.trim();
        const known = agents.find((a) => a.name.toLowerCase() === agentName?.toLowerCase());
        const calledAt = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(row.called_at ?? "") ? row.called_at.slice(0, 16).replace(" ", "T") : e.calledAt;
        const lang = row.language?.toLowerCase();
        return {
          ...e,
          agent: known ? known.id : agentName ? NEW_AGENT : e.agent,
          newAgentName: known ? "" : (agentName ?? ""),
          calledAt,
          language: lang === "marathi" || lang === "hinglish" ? lang : e.language,
          loanRef: row.loan_ref || e.loanRef,
          requested: ["true", "yes", "1"].includes(row.borrower_requested_time?.toLowerCase() ?? ""),
        };
      }),
    );
    toast(matched ? `Filled details for ${matched} file${matched === 1 ? "" : "s"} from the CSV.` : "No CSV rows matched the chosen file names.");
  };

  const submit = async () => {
    setFormError(undefined);
    const problems = entries.map((e) => {
      if (e.error) return e.error;
      if (!e.agent) return "Choose an agent.";
      if (e.agent === NEW_AGENT && !e.newAgentName.trim()) return "Enter the new agent's name.";
      if (!e.loanRef.trim()) return "Enter a loan reference.";
      if (!e.calledAt) return "Enter the call date and time.";
      return undefined;
    });
    if (problems.some(Boolean)) {
      setEntries((prev) => prev.map((e, i) => ({ ...e, error: problems[i] })));
      setFormError("Fix the highlighted files before uploading.");
      return;
    }
    if (api.demoMode && !passcode.trim()) {
      setFormError("Enter the demo passcode to upload.");
      return;
    }
    const metadata: UploadMetadata[] = entries.map((e) => ({
      filename: e.file.name,
      ...(e.agent === NEW_AGENT ? { agent_name: e.newAgentName.trim() } : { agent_id: e.agent }),
      called_at: istInputToIso(e.calledAt),
      language: e.language,
      loan_ref: e.loanRef.trim(),
      borrower_requested_time: e.requested,
    }));
    setBusy(true);
    try {
      const calls = await api.uploadCalls(
        entries.map((e) => e.file),
        metadata,
        {
          passcode: passcode.trim() || undefined,
          onProgress: (i, f) => setProgress((p) => ({ ...p, [entries[i].key]: f })),
        },
      );
      setStoredPasscode(passcode.trim());
      toast.success(`${calls.length} call${calls.length === 1 ? "" : "s"} queued for transcription.`);
      setEntries([]);
      setProgress({});
      onOpenChange(false);
      onUploaded();
    } catch (e) {
      if (e instanceof ApiError && e.code === "forbidden") clearStoredPasscode();
      setFormError(e instanceof Error ? e.message : "The upload failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const agentOptions = [...agents.map((a) => ({ value: a.id, label: a.name })), { value: NEW_AGENT, label: "New agent" }];

  return (
    <Sheet open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <SheetContent side="right" className="w-full sm:max-w-xl">
        <SheetHeader className="border-b">
          <SheetTitle>Upload calls</SheetTitle>
          <SheetDescription>Recordings from the lender&apos;s own dialer. wav, mp3, m4a, ogg or flac, up to 25 MB each.</SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
            }}
            className={cn(
              "flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition-colors duration-150",
              dragging ? "border-brand bg-brand-subtle" : "bg-surface",
            )}
          >
            <UploadCloud aria-hidden className="size-4 text-muted-foreground" />
            <p>Drop audio files here, or</p>
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
                <FileAudio aria-hidden data-icon="inline-start" />
                Choose files
              </Button>
              <Button variant="outline" size="sm" disabled={entries.length === 0} onClick={() => csvInput.current?.click()}>
                <FileSpreadsheet aria-hidden data-icon="inline-start" />
                Fill from CSV
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              CSV columns: filename, agent_name, called_at, language, loan_ref, borrower_requested_time. Times are read as IST.
            </p>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".wav,.mp3,.m4a,.ogg,.flac,audio/*"
              className="sr-only"
              aria-label="Audio files"
              onChange={(e) => {
                if (e.target.files) addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <input
              ref={csvInput}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="CSV with call details"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void applyCsv(f);
                e.target.value = "";
              }}
            />
          </div>

          {entries.map((e) => (
            <fieldset key={e.key} className={cn("space-y-3 rounded-lg border p-3", e.error && "border-critical/50")}>
              <legend className="sr-only">Details for {e.file.name}</legend>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-medium">{e.file.name}</p>
                  <p className="tnum text-xs text-muted-foreground">{(e.file.size / (1024 * 1024)).toFixed(1)} MB</p>
                </div>
                <Button variant="ghost" size="icon-sm" aria-label={`Remove ${e.file.name}`} disabled={busy} onClick={() => setEntries((p) => p.filter((x) => x.key !== e.key))}>
                  <X aria-hidden />
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Agent</Label>
                  <Select items={agentOptions} value={e.agent || null} onValueChange={(v) => patch(e.key, { agent: String(v ?? ""), error: undefined })}>
                    <SelectTrigger size="sm" aria-label={`Agent for ${e.file.name}`} className="w-full">
                      <SelectValue placeholder="Choose agent" />
                    </SelectTrigger>
                    <SelectContent alignItemWithTrigger={false}>
                      {agentOptions.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`loan-${e.key}`}>Loan reference</Label>
                  <Input id={`loan-${e.key}`} value={e.loanRef} onChange={(ev) => patch(e.key, { loanRef: ev.target.value, error: undefined })} className="font-mono" />
                </div>
                {e.agent === NEW_AGENT && (
                  <div className="col-span-2 space-y-1">
                    <Label htmlFor={`new-${e.key}`}>New agent name</Label>
                    <Input id={`new-${e.key}`} value={e.newAgentName} onChange={(ev) => patch(e.key, { newAgentName: ev.target.value, error: undefined })} />
                  </div>
                )}
                <div className="space-y-1">
                  <Label htmlFor={`at-${e.key}`}>Called at (IST)</Label>
                  <Input id={`at-${e.key}`} type="datetime-local" value={e.calledAt} onChange={(ev) => patch(e.key, { calledAt: ev.target.value, error: undefined })} className="tnum" />
                </div>
                <div className="space-y-1">
                  <Label>Language</Label>
                  <FilterSelect
                    label={`Language for ${e.file.name}`}
                    allLabel="Hinglish"
                    value={e.language === "marathi" ? "marathi" : undefined}
                    options={[{ value: "marathi", label: "Marathi" }]}
                    onChange={(v) => patch(e.key, { language: v === "marathi" ? "marathi" : "hinglish" })}
                    className="w-full"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2">
                <Checkbox checked={e.requested} onCheckedChange={(c) => patch(e.key, { requested: c === true })} />
                <span>Borrower asked for this call time</span>
              </label>
              {e.error && (
                <p role="alert" className="text-xs text-critical">
                  {e.error}
                </p>
              )}
              {busy && (
                <div className="h-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round((progress[e.key] ?? 0) * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Upload progress for ${e.file.name}`}>
                  <div className="h-full bg-brand transition-[width] duration-150" style={{ width: `${(progress[e.key] ?? 0) * 100}%` }} />
                </div>
              )}
            </fieldset>
          ))}

          {entries.length > 0 && api.demoMode && (
            <div className="space-y-1">
              <Label htmlFor="passcode">Demo passcode</Label>
              <Input id="passcode" type="password" autoComplete="off" value={passcode} onChange={(e) => setPasscode(e.target.value)} className="max-w-60" />
              <p className="text-xs text-muted-foreground">
                Uploads use transcription credits, so they need the passcode.
                {api.isMock && <> This build runs on mock data; the passcode is <span className="font-mono">{MOCK_PASSCODE_HINT}</span>.</>}
              </p>
            </div>
          )}
        </div>

        <SheetFooter className="border-t">
          {formError && (
            <p role="alert" className="text-critical">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button disabled={busy || entries.length === 0} onClick={() => void submit()}>
              {busy ? "Uploading" : entries.length === 0 ? "Upload" : `Upload ${entries.length} ${entries.length === 1 ? "call" : "calls"}`}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
