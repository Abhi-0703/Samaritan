import { cn } from "@/lib/utils";

/** Top bar, 56 px: title, one-line description, primary action on the right. */
export function PageHeader({
  title,
  description,
  actions,
  back,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  back?: React.ReactNode;
}) {
  return (
    <header className="no-print sticky top-12 z-20 border-b bg-background md:top-0">
      <div className="mx-auto flex h-14 w-full max-w-[1280px] items-center justify-between gap-4 px-4 sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          {back}
          <h1 className="shrink-0 text-base font-semibold">{title}</h1>
          {description && <p className="hidden truncate text-muted-foreground lg:block">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function PageContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1280px] space-y-6 px-4 py-6 sm:px-8 sm:py-8", className)}>{children}</div>;
}

export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("min-w-0", className)}>
      <div className="mb-3 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-semibold">{title}</h2>
          {description && <p className="text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
