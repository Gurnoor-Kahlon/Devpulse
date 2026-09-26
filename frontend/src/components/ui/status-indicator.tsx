const statuses = {
  operational: { label: "Operational", color: "text-success" },
  confirming: { label: "Confirming failure", color: "text-warning" },
  failing: { label: "Failing", color: "text-danger" },
  paused: { label: "Paused", color: "text-muted" },
  unknown: { label: "No data", color: "text-muted" },
  stale: { label: "Stale observations", color: "text-warning" },
  pending: { label: "Health not evaluated", color: "text-muted" },
} as const;

export type MonitorStatus = keyof typeof statuses;

export function StatusIndicator({ status }: { status: MonitorStatus }) {
  const { label, color } = statuses[status];

  return (
    <span
      className={`inline-flex items-center gap-2 text-xs font-medium ${color}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${status === "unknown" ? "border border-current" : "bg-current"}`}
      />
      {label}
    </span>
  );
}
