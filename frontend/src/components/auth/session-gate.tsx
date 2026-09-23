"use client";
import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { ApplicationShell } from "@/components/shell/application-shell";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiError, authPost, getMe, type User } from "@/lib/api/client";
import { leaveWorkspace } from "@/lib/auth/redirect";

export function SessionGate({
  initialUser,
  children,
}: {
  initialUser: User;
  children: ReactNode;
}) {
  const cache = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => getMe(signal),
    initialData: initialUser,
    refetchOnMount: "always",
  });
  const expired =
    session.error instanceof ApiError && session.error.status === 401;
  useEffect(() => {
    if (expired) {
      leaveWorkspace("expired");
    }
  }, [expired, cache]);
  useEffect(() => {
    const refresh = () => {
      void cache.invalidateQueries({ queryKey: ["session"] });
    };
    window.addEventListener("pageshow", refresh);
    return () => window.removeEventListener("pageshow", refresh);
  }, [cache]);
  const logout = useMutation({
    mutationFn: () => authPost("/api/v1/auth/logout", undefined),
    onSuccess: () => {
      cache.clear();
      leaveWorkspace("signed-out");
    },
  });
  if (expired || session.isFetching)
    return (
      <main className="p-8">
        <LoadingState label="Checking your session" />
      </main>
    );
  if (session.isError)
    return (
      <main className="mx-auto max-w-lg p-8">
        <ErrorState onRetry={() => void session.refetch()} />
      </main>
    );
  return (
    <ApplicationShell
      account={
        <Button
          variant="secondary"
          loading={logout.isPending}
          onClick={() => logout.mutate()}
        >
          Sign out
        </Button>
      }
    >
      {logout.isError && (
        <p role="alert" className="mb-4 text-danger">
          Sign out failed. Please try again.
        </p>
      )}
      <section
        aria-label="Account"
        className="mb-8 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4"
      >
        <div className="min-w-0">
          <p className="text-xs text-muted">Signed in as</p>
          <p className="break-all font-medium">{session.data.email}</p>
        </div>
        {session.data.email_verified_at ? (
          <span className="text-sm text-success">Email verified</span>
        ) : (
          <Link href="/verify-email" className="button button--secondary">
            Verify email
          </Link>
        )}
      </section>
      {children}
    </ApplicationShell>
  );
}
