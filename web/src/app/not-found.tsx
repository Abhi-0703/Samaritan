import Link from "next/link";
import { PageContent, PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <PageContent>
        <div className="flex flex-col items-start gap-3">
          <p className="text-muted-foreground">There is nothing at this address.</p>
          <Link href="/" className={buttonVariants({ variant: "outline" })}>
            Go to Overview
          </Link>
        </div>
      </PageContent>
    </>
  );
}
