import { Suspense } from "react";
import { AgentDetailView } from "@/components/agent-detail-view";
import { PageContent, PageHeader } from "@/components/page-header";
import { BlockSkeleton } from "@/components/states";

// These views fetch their data in the browser, so the route may block on its params instead of streaming a shell.
export const instant = false;

export default function AgentPage({ params }: PageProps<"/agents/[id]">) {
  return (
    <Suspense
      fallback={
        <>
          <PageHeader title="Agent" />
          <PageContent>
            <BlockSkeleton className="h-24" />
            <BlockSkeleton className="h-64" />
          </PageContent>
        </>
      }
    >
      {params.then(({ id }) => (
        <AgentDetailView id={id} />
      ))}
    </Suspense>
  );
}
