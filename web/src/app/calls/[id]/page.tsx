import { Suspense } from "react";
import { CallDetailView } from "@/components/call-detail-view";
import { PageContent, PageHeader } from "@/components/page-header";
import { BlockSkeleton } from "@/components/states";

function Fallback() {
  return (
    <>
      <PageHeader title="Call" />
      <PageContent>
        <BlockSkeleton className="h-20" />
        <BlockSkeleton className="h-96" />
      </PageContent>
    </>
  );
}

// These views fetch their data in the browser, so the route may block on its params instead of streaming a shell.
export const instant = false;

export default function CallPage({ params }: PageProps<"/calls/[id]">) {
  return (
    <Suspense fallback={<Fallback />}>
      {params.then(({ id }) => (
        <CallDetailView id={id} />
      ))}
    </Suspense>
  );
}
