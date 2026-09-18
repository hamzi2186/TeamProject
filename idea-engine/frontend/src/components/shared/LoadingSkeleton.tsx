import { Skeleton } from "@/components/ui/skeleton";

interface LoadingSkeletonProps {
  variant?: "table" | "cards";
  rows?: number;
}

export function LoadingSkeleton({ variant = "table", rows = 6 }: LoadingSkeletonProps) {
  if (variant === "cards") {
    return (
      <div className="grid gap-4">
        {Array.from({ length: Math.min(rows, 4) }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-3">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-72" />
                <Skeleton className="h-3 w-64" />
              </div>
              <Skeleton className="h-6 w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-24" />
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-6 px-5 py-3.5">
            <Skeleton className="h-3.5 w-28" />
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-3.5 w-14" />
            <Skeleton className="ml-auto h-3.5 w-24" />
          </div>
        ))}
      </div>
    </div>
  );
}