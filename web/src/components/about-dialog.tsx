"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function AboutDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>About Samaritan</DialogTitle>
          <DialogDescription className="sr-only">What Samaritan is, who it is for, how it uses Gnani Prisma and what data it holds.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">What it is. </span>
            Samaritan audits loan-recovery phone calls. It transcribes each recording, checks the agent&apos;s speech against nine
            recovery-conduct rules, and shows every finding with its exact quote, timestamp and rule.
          </p>
          <p>
            <span className="font-medium text-foreground">Who it is for. </span>
            Compliance and quality-assurance teams at banks, NBFCs and collection agencies, who can listen to only a small share of the
            calls their agents make.
          </p>
          <p>
            <span className="font-medium text-foreground">How it uses Gnani Prisma. </span>
            Speech-to-text comes from Gnani Prisma through its batch API with speaker separation. Rule matching, the language-model check,
            evidence verification, scoring and the accuracy figures are built in this project.
          </p>
          <p>
            <span className="font-medium text-foreground">About the data. </span>
            Everything in this workspace is synthetic. The calls are acted from scripts and no real borrower, phone number or account
            appears. Findings are decision support and need human review.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
