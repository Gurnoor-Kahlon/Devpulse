import Link from "next/link";
import type { ReactNode } from "react";

export function MonitorHeading({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="mb-2 text-[10px] font-semibold tracking-[0.18em] text-muted uppercase">
          Workspace / Monitors
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 max-w-lg text-sm text-muted">
          Save the endpoints you want to monitor. Health checks are not running
          yet.
        </p>
      </div>
      {children}
    </div>
  );
}

export function VerificationNotice() {
  return (
    <p className="mb-6 rounded-lg border border-border bg-surface p-4 text-sm text-warning">
      Verify your email before creating or enabling monitors.{" "}
      <Link href="/verify-email" className="underline underline-offset-4">
        Verify email
      </Link>
    </p>
  );
}
