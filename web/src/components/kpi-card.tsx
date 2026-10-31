import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  sub,
  loading,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  loading?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border p-4", className)}>
      <p className="text-xs text-muted-foreground">{label}</p>
      {loading ? (
        <>
          <Skeleton className="mt-2 h-6 w-16" />
          <Skeleton className="mt-2 h-3 w-24" />
        </>
      ) : (
        <>
          <p className="tnum mt-1 text-2xl font-semibold">{value}</p>
          {sub && <p className="tnum mt-0.5 text-xs text-muted-foreground">{sub}</p>}
        </>
      )}
    </div>
  );
}
