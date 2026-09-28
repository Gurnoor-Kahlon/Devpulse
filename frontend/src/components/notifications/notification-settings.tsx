"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiError } from "@/lib/api/client";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from "@/lib/api/notifications";
import { DeliveryList } from "./delivery-list";

function PreferencesForm({
  initial,
  reload,
  reloading,
}: {
  initial: NotificationPreferences;
  reload: () => void;
  reloading: boolean;
}) {
  const cache = useQueryClient();
  const [enabled, setEnabled] = useState(initial.enabled);
  const [onOpen, setOnOpen] = useState(initial.on_open);
  const [onRecovery, setOnRecovery] = useState(initial.on_recovery);
  const [version, setVersion] = useState(initial.configuration_version);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [conflict, setConflict] = useState(false);
  return (
    <form
      className="max-w-2xl space-y-5 rounded-lg border border-border bg-surface p-5"
      onSubmit={async (event) => {
        event.preventDefault();
        setSaving(true);
        setError("");
        setMessage("");
        try {
          const saved = await updateNotificationPreferences({
            configuration_version: version,
            enabled,
            on_open: onOpen,
            on_recovery: onRecovery,
          });
          setVersion(saved.configuration_version);
          setConflict(false);
          setMessage("Notification preferences saved.");
          void cache.invalidateQueries({
            queryKey: ["notification-deliveries"],
          });
        } catch (cause) {
          const stale = cause instanceof ApiError && cause.status === 409;
          setConflict(stale);
          setError(
            stale
              ? "Preferences changed in another session. Your edits are preserved. Reload saved preferences before trying again."
              : cause instanceof ApiError &&
                  cause.code === "email_verification_required"
                ? "Verify your account email before enabling notifications."
                : "Could not confirm the save. Your edits are preserved. Reload to check the saved preferences.",
          );
        } finally {
          setSaving(false);
        }
      }}
    >
      <h2 className="text-xl font-semibold">Incident email preferences</h2>
      <p className="break-all text-sm">Destination: {initial.destination}</p>
      {!initial.verified && (
        <p className="text-sm text-warning">
          Verify your account email to enable incident notifications.{" "}
          <Link href="/verify-email" className="underline">
            Verify email
          </Link>
        </p>
      )}
      <fieldset disabled={saving || reloading} className="space-y-4">
        <legend className="sr-only">Incident email options</legend>
        <label className="flex items-start gap-3">
          <input
            className="mt-1 accent-accent"
            type="checkbox"
            checked={enabled}
            disabled={!initial.verified && !enabled}
            onChange={(e) => {
              setEnabled(e.target.checked);
              setMessage("");
            }}
          />
          Enable incident email
        </label>
        <label className="flex items-start gap-3">
          <input
            className="mt-1 accent-accent"
            type="checkbox"
            checked={onOpen}
            onChange={(e) => {
              setOnOpen(e.target.checked);
              setMessage("");
            }}
          />
          Email when an incident is confirmed
        </label>
        <label className="flex items-start gap-3">
          <input
            className="mt-1 accent-accent"
            type="checkbox"
            checked={onRecovery}
            onChange={(e) => {
              setOnRecovery(e.target.checked);
              setMessage("");
            }}
          />
          Email when recovery is observed
        </label>
      </fieldset>
      <p className="text-sm text-muted">
        Applies to future transitions across your monitors. Confirmation follows
        three failed attempts; one successful scheduled attempt records
        recovery. Pausing or archiving a monitor does not send a recovery email.
      </p>
      <p className="text-sm text-muted">
        Disabling an option stops queued mail and further retries for that
        transition. An email already being sent cannot be recalled. Re-enabling
        does not resend earlier events.
      </p>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="text-success">
          {message}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" loading={saving} disabled={reloading || conflict}>
          Save preferences
        </Button>
        <Button
          variant="secondary"
          loading={reloading}
          disabled={saving}
          onClick={reload}
        >
          Reload saved preferences
        </Button>
      </div>
      <p className="text-xs text-muted">
        Reload replaces unsaved edits. Preference version {version}.
      </p>
    </form>
  );
}

export function NotificationSettings() {
  const query = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: ({ signal }) => getNotificationPreferences(signal),
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-3xl font-semibold">Notifications</h1>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Receive confirmed incident and recovery emails at your verified
          account address.
        </p>
      </div>
      {query.isPending ? (
        <LoadingState label="Loading notification preferences" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="text-danger">
              Could not reload preferences. Your edits are preserved.
            </p>
          )}
          <PreferencesForm
            key={query.dataUpdatedAt}
            initial={query.data}
            reload={() => void query.refetch()}
            reloading={query.isFetching}
          />
        </>
      )}
      <DeliveryList />
    </div>
  );
}
