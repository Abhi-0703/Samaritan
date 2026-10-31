import type { Metadata } from "next";
import { AccuracyView } from "@/components/accuracy-view";

export const metadata: Metadata = { title: "Accuracy" };

export default function AccuracyPage() {
  return <AccuracyView />;
}
