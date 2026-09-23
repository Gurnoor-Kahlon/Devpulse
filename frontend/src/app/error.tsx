"use client";
import { ErrorState } from "@/components/ui/error-state";
export default function ApplicationError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-lg px-5 py-20">
      <ErrorState onRetry={reset} />
    </main>
  );
}
