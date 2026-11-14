import type { Metadata } from "next";
import { Suspense } from "react";
import { TryFlow } from "@/components/try/try-flow";

export const metadata: Metadata = {
  title: "Analyse a call",
  description: "Upload a loan-recovery call and see Samaritan's analysis once it has been transcribed.",
};

export default function TryPage() {
  // CallDetailView reads search parameters, so it needs a Suspense boundary to render under Cache Components.
  return (
    <Suspense fallback={null}>
      <TryFlow />
    </Suspense>
  );
}
