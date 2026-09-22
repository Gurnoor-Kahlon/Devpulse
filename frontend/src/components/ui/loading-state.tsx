export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />;
}

export function LoadingState({
  label = "Loading overview",
}: {
  label?: string;
}) {
  return (
    <div role="status" aria-live="polite" className="space-y-8">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className="space-y-3">
        <Skeleton className="h-8 w-44" />
        <Skeleton className="h-4 w-3/4 max-w-sm" />
      </div>
      <div
        aria-hidden="true"
        className="space-y-5 rounded-lg border border-border bg-surface p-6"
      >
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-48 w-full" />
      </div>
    </div>
  );
}
