import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-5 sm:px-8">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border py-5">
        <Link
          href="/"
          aria-label="DevPulse home"
          className="flex min-h-11 items-center gap-3 font-semibold"
        >
          <Icon name="pulse" className="text-accent" /> DevPulse
        </Link>
        <nav
          aria-label="Public navigation"
          className="flex flex-wrap items-center gap-2"
        >
          <Link href="/demo" className="button button--ghost min-h-11">
            Explore demo
          </Link>
          <Link href="/login" className="button button--secondary min-h-11">
            Sign in
          </Link>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1} className="min-w-0 py-12 sm:py-16">
        {children}
      </main>
      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-border py-8 text-sm text-muted">
        <p>DevPulse · Reliability at a glance.</p>
        <Link
          href="/register"
          className="inline-flex min-h-11 items-center text-accent underline underline-offset-4"
        >
          Create an account
        </Link>
      </footer>
    </div>
  );
}
