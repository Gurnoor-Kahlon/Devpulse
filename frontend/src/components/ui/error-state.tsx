"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export function ErrorState({
  title = "This view couldn't be loaded",
  description = "Please try again. If the problem continues, come back in a moment.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry: () => void;
}) {
  return (
    <section className="rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <div role="alert">
        <Icon
          name="alert"
          className="mx-auto mb-5 text-danger"
          width="28"
          height="28"
        />
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
          {description}
        </p>
      </div>
      <Button variant="secondary" onClick={onRetry} className="mt-6">
        <Icon name="refresh" />
        Try again
      </Button>
    </section>
  );
}
