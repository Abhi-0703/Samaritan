import { Suspense } from "react";
import { EvidenceView } from "@/components/evidence-view";
import { PageContent, PageHeader } from "@/components/page-header";
import { BlockSkeleton } from "@/components/states";

// These views fetch their data in the browser, so the route may block on its params instead of streaming a shell.
export const instant = false;

export default function EvidencePage({ params }: PageProps<"/calls/[id]/evidence">) {
  return (
    <Suspense
      fallback={
        <>
          <PageHeader title="Evidence summary" />
          <PageContent>
            <BlockSkeleton className="h-64" />
          </PageContent>
        </>
      }
    >
      {params.then(({ id }) => (
        <EvidenceView id={id} />
      ))}
    </Suspense>
  );
}
