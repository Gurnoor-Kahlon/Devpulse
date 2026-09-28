"use client";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { getDeliveries, type Delivery } from "@/lib/api/notifications";
import { usePollingQuery } from "@/lib/use-polling-query";

const labels: Record<Delivery["status"], string> = {
  pending: "Pending",
  sending: "Sending",
  sent: "Accepted by SMTP",
  failed: "Failed",
  cancelled: "Cancelled",
};
const reasons: Record<NonNullable<Delivery["last_error_code"]>, string> = {
  smtp_unavailable:
    "The email service was unavailable or its response was uncertain.",
  smtp_rejected: "The email service rejected this attempt.",
  delivery_unknown:
    "The attempt limit was reached after interrupted sends. Acceptance is unknown.",
  preferences_disabled:
    "Further sending was stopped by your notification preferences.",
  email_unverified: "A verified account email is required.",
};
const date = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";

export function DeliveryList({ incidentId }: { incidentId?: string }) {
  const [cursor, setCursor] = useState<string>();
  const query = usePollingQuery(
    ["notification-deliveries", incidentId, cursor],
    (signal) => getDeliveries({ incidentId, cursor }, signal),
  );
  return (
    <section aria-label="Email delivery history" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Email delivery history</h2>
        <Button
          variant="secondary"
          loading={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh deliveries
        </Button>
      </div>
      <p className="text-sm text-muted">
        Accepted by SMTP means the email service accepted the message, not that
        it reached your inbox. Interrupted sends can produce duplicates.
        Delivery failures do not change monitor health.
      </p>
      {query.isPending ? (
        <LoadingState label="Loading email deliveries" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="text-danger">
              Delivery refresh failed. Showing the last loaded status.
            </p>
          )}
          {query.data.items.length === 0 ? (
            <EmptyState
              title="No recorded email deliveries"
              description="Email is opt-in and applies to future incident transitions. Earlier events are not sent retroactively."
            />
          ) : (
            <ul aria-label="Email deliveries" className="space-y-3">
              {query.data.items.map((item) => (
                <li
                  key={item.id}
                  className="min-w-0 rounded-lg border border-border bg-surface p-5"
                >
                  <div className="flex flex-wrap justify-between gap-3">
                    <p className="font-medium">
                      {item.transition === "opened"
                        ? "Incident confirmed"
                        : "Recovery observed"}
                    </p>
                    <span
                      className={
                        item.status === "failed"
                          ? "text-danger"
                          : item.status === "sent"
                            ? "text-success"
                            : "text-muted"
                      }
                    >
                      {labels[item.status]}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    Created {date(item.created_at)} · {item.attempt_count} of 5
                    attempts
                  </p>
                  {item.next_attempt_at && (
                    <p className="mt-2 text-xs text-muted">
                      Eligible to send after {date(item.next_attempt_at)}
                    </p>
                  )}
                  {item.completed_at && (
                    <p className="mt-2 text-xs text-muted">
                      Completed {date(item.completed_at)}
                    </p>
                  )}
                  {item.cancel_requested && item.status === "sending" && (
                    <p className="mt-2 text-sm">
                      Stopping further attempts; the current send may already
                      have been accepted.
                    </p>
                  )}
                  {item.last_error_code && (
                    <p className="mt-2 text-sm text-muted">
                      {reasons[item.last_error_code]}
                    </p>
                  )}
                  {!incidentId && (
                    <Link
                      className="mt-3 inline-block text-sm underline"
                      href={`/incidents/${item.incident_id}`}
                    >
                      View incident
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setCursor(undefined);
                if (!cursor) void query.refetch();
              }}
            >
              Newest deliveries
            </Button>
            {query.data.next_cursor && (
              <Button
                variant="secondary"
                onClick={() => setCursor(query.data!.next_cursor!)}
              >
                Older deliveries
              </Button>
            )}
          </div>
        </>
      )}
      <p className="text-xs text-muted">
        Refreshes stored status while this page is visible. Sending is handled
        in the background.
      </p>
    </section>
  );
}
