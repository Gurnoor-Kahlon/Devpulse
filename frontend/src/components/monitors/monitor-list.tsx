"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAccount } from "@/components/auth/session-gate";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { TextField } from "@/components/ui/text-field";
import { ApiError } from "@/lib/api/client";
import {
  archiveMonitor,
  listMonitors,
  updateMonitor,
  type Monitor,
} from "@/lib/api/monitors";
import { MonitorHeading, VerificationNotice } from "./monitor-heading";

function health(monitor: Monitor) {
  if (!monitor.enabled) return "paused";
  if (monitor.current_state === "down") return "failing";
  if (monitor.current_state === "confirming_failure") return "confirming";
  if (monitor.current_state === "unknown" && monitor.last_completed_check_at)
    return "pending";
  return monitor.current_state;
}

function ArchiveButton({
  monitor,
  onArchived,
  disabled,
}: {
  monitor: Monitor;
  onArchived: () => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const cancel = useRef<HTMLButtonElement>(null);
  // Keep the version the user actually reviewed, even if the list refreshes behind the dialog.
  const [reviewed, setReviewed] = useState(monitor);
  const mutation = useMutation({
    mutationFn: () => archiveMonitor(reviewed),
    onSuccess: () => {
      setOpen(false);
      onArchived();
    },
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (mutation.isPending) return;
        if (value) {
          setReviewed(monitor);
          mutation.reset();
        }
        setOpen(value);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" disabled={disabled}>
          Archive
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Archive monitor?"
        closeDisabled={mutation.isPending}
        description={`Archive “${reviewed.name}”? This removes it from your list and prevents future checks. Stored history is retained. You cannot undo this here.`}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancel.current?.focus();
        }}
      >
        {mutation.isError && (
          <p role="alert" className="mb-4 text-sm text-danger">
            {mutation.error instanceof ApiError
              ? mutation.error.message
              : "Archive failed. Try again."}
            {mutation.error instanceof ApiError &&
              mutation.error.status === 409 &&
              " Cancel and refresh the list to review the current monitor."}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-3">
          <DialogClose asChild>
            <Button
              ref={cancel}
              variant="secondary"
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
          </DialogClose>
          <Button
            className="text-danger"
            variant="secondary"
            loading={mutation.isPending}
            disabled={
              mutation.error instanceof ApiError &&
              mutation.error.status === 409
            }
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Archiving…" : "Archive monitor"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function MonitorList() {
  const account = useAccount();
  const verified = Boolean(account.email_verified_at);
  const cache = useQueryClient();
  const heading = useRef<HTMLDivElement>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [notice, setNotice] = useState("");
  const query = useQuery({
    queryKey: ["monitors"],
    queryFn: ({ signal }) => listMonitors(signal),
  });
  const toggle = useMutation({
    mutationFn: (monitor: Monitor) =>
      updateMonitor(monitor.id, {
        configuration_version: monitor.configuration_version,
        enabled: !monitor.enabled,
      }),
    onSuccess: async (monitor) => {
      cache.setQueryData<Monitor[]>(["monitors"], (items) =>
        items?.map((item) => (item.id === monitor.id ? monitor : item)),
      );
      setNotice(
        monitor.enabled
          ? "Monitor enabled. Automatic checks are not running yet."
          : "Monitor paused.",
      );
      await cache.invalidateQueries({ queryKey: ["monitors"] });
    },
  });
  const rows =
    query.data?.filter((monitor) => {
      const matches = `${monitor.name} ${monitor.url}`
        .toLowerCase()
        .includes(search.trim().toLowerCase());
      return (
        matches &&
        (filter === "all" ||
          (filter === "enabled" ? monitor.enabled : !monitor.enabled))
      );
    }) ?? [];
  return (
    <>
      <div ref={heading} tabIndex={-1}>
        <MonitorHeading title="Monitors">
          {verified && (
            <Link href="/monitors/new" className="button button--primary">
              Create monitor
            </Link>
          )}
        </MonitorHeading>
      </div>
      {!verified && <VerificationNotice />}
      {query.isPending ? (
        <LoadingState label="Loading monitors" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          <div className="mb-6 grid items-end gap-4 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
            <TextField
              label="Search monitors"
              type="search"
              placeholder="Name or URL"
              value={search}
              maxLength={2048}
              onChange={(event) => setSearch(event.target.value)}
            />
            <div className="space-y-2">
              <label
                htmlFor="monitor-filter"
                className="block text-sm font-medium"
              >
                Configuration
              </label>
              <select
                id="monitor-filter"
                className="text-field"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              >
                <option value="all">All monitors</option>
                <option value="enabled">Enabled</option>
                <option value="paused">Paused</option>
              </select>
            </div>
            <Button
              variant="secondary"
              loading={query.isFetching}
              disabled={toggle.isPending}
              onClick={() => {
                toggle.reset();
                void query.refetch();
              }}
            >
              Refresh list
            </Button>
          </div>
          <p className="mb-4 text-xs text-muted" role="status">
            {rows.length} of {query.data.length} monitors · 10 per account
          </p>
          {notice && (
            <p role="status" className="mb-4 text-sm text-success">
              {notice}
            </p>
          )}
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Refresh failed. Showing the last loaded list. Try Refresh list
              again.
            </p>
          )}
          {toggle.isError && (
            <p role="alert" className="mb-4 text-danger">
              {toggle.error instanceof ApiError
                ? toggle.error.message
                : "The change failed. Try again."}
            </p>
          )}
          {query.data.length === 0 ? (
            <EmptyState
              title="No monitors yet"
              description="Add an endpoint and choose its check settings. Results will appear after health checks become available."
            />
          ) : rows.length === 0 ? (
            <EmptyState
              title="No matching monitors"
              description="Try another name, URL, or configuration filter."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch("");
                    setFilter("all");
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ) : (
            <ul aria-label="Monitors" className="space-y-3">
              {rows.map((monitor) => (
                <li
                  key={monitor.id}
                  className="rounded-lg border border-border bg-surface p-5"
                >
                  <article
                    aria-label={monitor.name}
                    className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
                  >
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2">
                        <h2 className="min-w-0 break-words font-semibold">
                          <Link
                            className="hover:underline"
                            href={`/monitors/${monitor.id}/edit`}
                          >
                            {monitor.name}
                          </Link>
                        </h2>
                        <StatusIndicator status={health(monitor)} />
                      </div>
                      <p className="break-all font-mono text-xs text-muted">
                        {monitor.url}
                      </p>
                      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
                        <div>
                          <dt className="inline">Request: </dt>
                          <dd className="inline font-mono">
                            {monitor.method} · HTTP {monitor.expected_status}
                          </dd>
                        </div>
                        <div>
                          <dt className="inline">Interval: </dt>
                          <dd className="inline">
                            {monitor.interval_seconds}s
                          </dd>
                        </div>
                        <div>
                          <dt className="inline">Latest check: </dt>
                          <dd className="inline">
                            {monitor.last_completed_check_at
                              ? new Date(
                                  monitor.last_completed_check_at,
                                ).toLocaleString()
                              : "Never checked"}
                          </dd>
                        </div>
                      </dl>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/monitors/${monitor.id}/edit`}
                        className="button button--secondary"
                      >
                        Edit<span className="sr-only"> {monitor.name}</span>
                      </Link>
                      <Button
                        variant="secondary"
                        loading={
                          toggle.isPending &&
                          toggle.variables?.id === monitor.id
                        }
                        disabled={
                          toggle.isPending || (!verified && !monitor.enabled)
                        }
                        onClick={() => {
                          setNotice("");
                          toggle.mutate(monitor);
                        }}
                      >
                        {monitor.enabled ? "Pause" : "Resume"}
                      </Button>
                      <ArchiveButton
                        monitor={monitor}
                        disabled={toggle.isPending}
                        onArchived={() => {
                          setNotice(
                            "Monitor archived. Stored history is retained.",
                          );
                          cache.setQueryData<Monitor[]>(["monitors"], (items) =>
                            items?.filter((item) => item.id !== monitor.id),
                          );
                          void cache.invalidateQueries({
                            queryKey: ["monitors"],
                          });
                          requestAnimationFrame(() => heading.current?.focus());
                        }}
                      />
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}
