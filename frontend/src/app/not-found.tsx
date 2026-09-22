import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col items-start justify-center px-6 py-12">
      <p className="mb-4 font-mono text-xs text-muted">404 / Page not found</p>
      <h1 className="text-2xl font-semibold tracking-tight">
        This page isn’t here
      </h1>
      <p className="mt-3 text-sm text-muted">
        The address may have changed. Return to your workspace to continue.
      </p>
      <Link href="/dashboard" className="button button--primary mt-6">
        Back to overview
      </Link>
    </main>
  );
}
