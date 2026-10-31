"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, MOCK_PASSCODE_HINT } from "@/lib/api";
import { clearStoredPasscode, getStoredPasscode, setStoredPasscode } from "@/lib/passcode";
import { ApiError } from "@/lib/types";

type Action = (passcode: string | undefined) => Promise<void>;

/**
 * Actions that spend credits (retry, swap roles) need the demo passcode when the API runs in demo mode.
 * `gate(action)` runs the action straight away outside demo mode, or after the passcode is known.
 */
export function usePasscodeGate() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [message, setMessage] = useState<string>();
  const pending = useRef<Action | null>(null);

  const run = async (action: Action, passcode: string | undefined) => {
    try {
      await action(passcode);
    } catch (e) {
      if (e instanceof ApiError && e.code === "forbidden") {
        clearStoredPasscode();
        pending.current = action;
        setMessage("That passcode was not accepted. Try again.");
        setOpen(true);
        return;
      }
      toast.error(e instanceof Error ? e.message : "Something went wrong. Try again.");
    }
  };

  const gate = (action: Action) => {
    if (!api.demoMode) {
      void run(action, undefined);
      return;
    }
    const stored = getStoredPasscode();
    if (stored) {
      void run(action, stored);
      return;
    }
    pending.current = action;
    setMessage(undefined);
    setOpen(true);
  };

  const dialog = (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const code = value.trim();
            if (!code || !pending.current) return;
            setStoredPasscode(code);
            setOpen(false);
            setValue("");
            void run(pending.current, code);
          }}
          className="grid gap-4"
        >
          <DialogHeader>
            <DialogTitle>Demo passcode</DialogTitle>
            <DialogDescription>
              This action uses transcription or language-model credits, so the public demo asks for a passcode.
              {api.isMock && <> This build runs on mock data; the passcode is <span className="font-mono">{MOCK_PASSCODE_HINT}</span>.</>}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="gate-passcode">Passcode</Label>
            <Input id="gate-passcode" type="password" autoComplete="off" autoFocus value={value} onChange={(e) => setValue(e.target.value)} />
            {message && (
              <p role="alert" className="text-xs text-critical">
                {message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!value.trim()}>
              Continue
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  return { gate, dialog };
}
