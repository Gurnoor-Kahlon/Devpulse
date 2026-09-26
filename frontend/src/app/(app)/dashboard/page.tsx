import type { Metadata } from "next";

import { AboutDialog } from "@/components/shell/about-dialog";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export const metadata: Metadata = { title: "Overview · DevPulse" };

export default function OverviewPage() {
  return (
    <>
      <div className="mb-8 sm:mb-10">
        <p className="mb-2 text-[10px] font-semibold tracking-[0.18em] text-muted uppercase">
          Workspace
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-2 max-w-lg text-sm text-muted">
          Your monitors and reliability history, in one place.
        </p>
      </div>
      <section
        aria-label="Monitoring activity"
        className="overflow-hidden rounded-lg border border-border bg-surface"
      >
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
          <p className="text-sm font-medium">Monitoring activity</p>
        </div>
        <EmptyState
          title="Overview analytics are not available yet"
          description="Use Monitors for the latest health states and Incidents for confirmed failures and observed recoveries."
          action={
            <AboutDialog
              trigger={<Button variant="secondary">About this preview</Button>}
            />
          }
        />
      </section>
    </>
  );
}
