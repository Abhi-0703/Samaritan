import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: { absolute: "Samaritan: AI auditor for loan-recovery calls" },
  description: "Upload a recovery call and Samaritan finds every RBI-style conduct violation, pinned on the waveform.",
};

export default function HomePage() {
  return <LandingPage />;
}
