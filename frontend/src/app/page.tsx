import Image from "next/image";
import Link from "next/link";
import { PublicShell } from "@/components/public/public-shell";

export default function HomePage() {
  return (
    <PublicShell>
      <section
        className="max-w-3xl pb-14 sm:pb-20"
        aria-labelledby="landing-title"
      >
        <p className="mb-4 text-xs font-semibold tracking-widest text-accent uppercase">
          API monitoring, with evidence
        </p>
        <h1
          id="landing-title"
          className="text-4xl leading-tight font-semibold tracking-tight sm:text-6xl"
        >
          Reliability at a glance.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted">
          See what your endpoints returned, follow failures through recovery,
          and understand the observations behind your uptime.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/register" className="button button--primary min-h-11">
            Start monitoring
          </Link>
          <Link href="/demo" className="button button--secondary min-h-11">
            Explore the read-only demo
          </Link>
        </div>
        <p className="mt-4 text-sm text-muted">
          Create an account and verify your email to add your first monitor.
        </p>
      </section>
      <section aria-labelledby="features-title">
        <h2 id="features-title" className="text-2xl font-semibold">
          From a check to a clear incident history
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            [
              "Check the response",
              "Schedule HTTP checks and validate status, text, or JSON values. Review the saved outcome of each attempt.",
            ],
            [
              "Follow the failure",
              "Failures are retried before an incident is confirmed. Keep the opening evidence and see when recovery was observed.",
            ],
            [
              "Understand the numbers",
              "Explore uptime and response latency with observation counts and visible gaps. Enable incident emails in your workspace.",
            ],
          ].map(([title, description], i) => (
            <article
              key={title}
              className="rounded-lg border border-border bg-surface p-6"
            >
              <p
                aria-hidden="true"
                className="mb-5 font-mono text-sm text-accent"
              >
                0{i + 1}
              </p>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-3 text-sm text-muted">{description}</p>
            </article>
          ))}
        </div>
      </section>
      <section aria-labelledby="preview-title" className="mt-16">
        <h2 id="preview-title" className="text-2xl font-semibold">
          A look inside the demo
        </h2>
        <p className="mt-3 max-w-2xl text-muted">
          A real local capture of a controlled failure and recovery exercise.
          The demo reads stored monitoring results; exploring it never sends a
          probe.
        </p>
        <figure className="mt-6 overflow-hidden rounded-lg border border-border bg-surface">
          <Image
            src="/screenshots/demo-desktop.png"
            alt="DevPulse demo showing a labeled controlled failure, observed uptime, latency, and recorded incident times."
            width={1280}
            height={1758}
            className="h-auto w-full"
            sizes="(max-width: 1152px) 100vw, 1088px"
          />
          <figcaption className="border-t border-border p-4 text-sm text-muted">
            Actual browser capture from real loopback HTTP probes in an isolated
            test database. Static illustration of the product, not current
            service availability.{" "}
            <Link
              href="/screenshots/demo-mobile.png"
              className="inline-flex min-h-11 items-center text-accent underline"
            >
              View the mobile capture
            </Link>
            .
          </figcaption>
        </figure>
      </section>
      <section
        className="mt-16 rounded-lg border border-border bg-surface p-6 sm:p-8"
        aria-labelledby="start-title"
      >
        <h2 id="start-title" className="text-2xl font-semibold">
          Bring your own endpoints.
        </h2>
        <p className="mt-3 text-muted">
          Your workspace keeps monitor configuration and detailed evidence
          private. The public demo shows only explicitly approved summaries.
        </p>
        <Link href="/register" className="button button--primary mt-6 min-h-11">
          Create your account
        </Link>
      </section>
    </PublicShell>
  );
}
