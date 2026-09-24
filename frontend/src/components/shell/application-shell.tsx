import Link from "next/link";
import type { ReactNode } from "react";

import { AboutDialog } from "@/components/shell/about-dialog";
import { MobileNavigation } from "@/components/shell/mobile-navigation";
import { WorkspaceNavigation } from "@/components/shell/workspace-navigation";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export function ApplicationShell({
  children,
  account,
}: {
  children: ReactNode;
  account?: ReactNode;
}) {
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[232px_minmax(0,1fr)]">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-border bg-surface md:flex">
        <Link
          href="/dashboard"
          aria-label="DevPulse overview"
          className="mx-6 mt-7 mb-12 flex w-fit items-center gap-3 rounded-sm"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-elevated text-accent">
            <Icon name="pulse" width="22" height="22" />
          </span>
          <span className="text-lg font-semibold tracking-tight">DevPulse</span>
        </Link>
        <div className="px-4">
          <WorkspaceNavigation />
        </div>
        <div className="mt-auto p-4">
          <AboutDialog
            trigger={
              <Button variant="ghost" className="w-full justify-start">
                <Icon name="info" /> About DevPulse
              </Button>
            }
          />
          <p className="mt-4 border-t border-border px-3 pt-5 pb-2 text-xs text-muted">
            Reliability at a glance.
          </p>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="flex h-16 items-center justify-between gap-3 border-b border-border px-4 sm:px-8 lg:px-12">
          <div className="flex min-w-0 items-center gap-3">
            <MobileNavigation />
            <span className="text-sm font-semibold md:hidden">DevPulse</span>
            <div className="hidden items-center gap-3 text-xs md:flex">
              <span className="text-muted">Workspace</span>
              <span aria-hidden="true" className="text-muted">
                /
              </span>
              <span>Personal account</span>
            </div>
          </div>
          {account ?? (
            <span className="rounded-sm border border-border px-2 py-1 font-mono text-[10px] tracking-wide text-muted">
              Interface preview
            </span>
          )}
        </header>
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto max-w-6xl px-5 py-8 outline-none sm:px-8 sm:py-10 lg:px-12 lg:py-12"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
