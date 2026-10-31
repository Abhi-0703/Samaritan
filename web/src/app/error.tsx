"use client";

import { PageContent, PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";

export default function GlobalError({ error, unstable_retry }: { error: Error & { digest?: string }; unstable_retry: () => void }) {
  return (
    <>
      <PageHeader title="Something went wrong" />
      <PageContent>
        <ErrorState title="This page could not be shown" message={error.message} onRetry={unstable_retry} />
      </PageContent>
    </>
  );
}
