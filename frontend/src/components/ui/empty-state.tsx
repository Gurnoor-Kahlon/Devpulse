import type { ReactNode } from "react";

import { Icon } from "@/components/ui/icon";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center sm:py-24">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-lg border border-border bg-elevated text-accent">
        <Icon name="pulse" width="28" height="28" />
      </div>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
