import type { Metadata } from "next";
import { PublicShell } from "@/components/public/public-shell";
import { DemoView } from "@/components/public/demo-view";

export const metadata: Metadata = { title: "Read-only demo · DevPulse" };
export default function DemoPage() {
  return (
    <PublicShell>
      <p className="mb-3 text-xs font-semibold tracking-widest text-accent uppercase">
        Public · Read only
      </p>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
        Monitoring, with the evidence in view.
      </h1>
      <p className="mt-4 mb-8 max-w-3xl text-muted">
        Explore explicitly published monitors and their stored results.
        Controlled failures are labeled. Private endpoint URLs, account details,
        and response evidence are not published.
      </p>
      <DemoView />
    </PublicShell>
  );
}
