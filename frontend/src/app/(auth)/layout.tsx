import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh px-5 py-8 sm:py-12">
      <a href="#account-content" className="skip-link">
        Skip to content
      </a>
      <header className="mx-auto mb-10 flex max-w-md items-center justify-between gap-4">
        <Link
          href="/"
          className="flex items-center gap-3 text-lg font-semibold"
        >
          <span className="rounded-md border border-border bg-surface p-2 text-accent">
            <Icon name="pulse" />
          </span>
          DevPulse
        </Link>
        <span className="text-xs text-muted">Reliability at a glance.</span>
      </header>
      <main
        id="account-content"
        tabIndex={-1}
        className="mx-auto max-w-md rounded-lg border border-border bg-surface p-6 outline-none sm:p-8"
      >
        {children}
      </main>
      <p className="mx-auto mt-6 max-w-md text-center text-xs text-muted">
        A focused workspace for API reliability.
      </p>
    </div>
  );
}
