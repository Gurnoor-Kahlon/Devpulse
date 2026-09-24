"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAccount } from "@/components/auth/session-gate";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { ApiError } from "@/lib/api/client";
import {
  createMonitor,
  updateMonitor,
  type Monitor,
  type MonitorCreate,
  type MonitorUpdate,
} from "@/lib/api/monitors";
import { VerificationNotice } from "./monitor-heading";

export function MonitorForm({
  monitor,
  onReload,
  reloading = false,
}: {
  monitor?: Monitor;
  onReload?: () => void;
  reloading?: boolean;
}) {
  const [baseline] = useState(monitor);
  const account = useAccount();
  const verified = Boolean(account.email_verified_at);
  const router = useRouter();
  const cache = useQueryClient();
  const summary = useRef<HTMLDivElement>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const focusError = () =>
    requestAnimationFrame(() => summary.current?.focus());
  const mutation = useMutation({
    mutationFn: (body: MonitorCreate) => {
      if (!baseline) return createMonitor(body);
      const changes: MonitorUpdate = {
        configuration_version: baseline.configuration_version,
      };
      for (const key of [
        "name",
        "url",
        "method",
        "expected_status",
        "interval_seconds",
        "timeout_seconds",
        "enabled",
      ] as const) {
        if (body[key] !== baseline[key])
          Object.assign(changes, { [key]: body[key] });
      }
      if (Object.keys(changes).length === 1) changes.name = body.name;
      return updateMonitor(baseline.id, changes);
    },
    onSuccess: async (saved) => {
      cache.setQueryData<Monitor[]>(["monitors"], (items) => {
        if (!items) return items;
        return baseline
          ? items.map((item) => (item.id === saved.id ? saved : item))
          : [saved, ...items];
      });
      await cache.invalidateQueries({ queryKey: ["monitors"] });
      if (baseline) cache.removeQueries({ queryKey: ["monitor", baseline.id] });
      router.push("/monitors");
    },
    onError: (error) => {
      setMessage(
        error instanceof ApiError
          ? error.message
          : "We could not save this monitor. Try again.",
      );
      if (error instanceof ApiError) {
        const fields: Record<string, string> = {};
        for (const field of error.fields ?? []) {
          if (field.field.startsWith("body."))
            fields[field.field.slice(5)] = field.message;
        }
        setErrors(fields);
      }
      focusError();
    },
  });
  const conflict =
    mutation.error instanceof ApiError &&
    mutation.error.code === "configuration_conflict";
  const missing =
    mutation.error instanceof ApiError && mutation.error.status === 404;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending || conflict || missing) return;
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") ?? "").trim();
    const url = String(data.get("url") ?? "");
    const nextErrors: Record<string, string> = {};
    if (!name || name.length > 100)
      nextErrors.name = "Enter a name from 1 to 100 characters.";
    try {
      const parsed = new URL(url);
      const authority = url.split("://")[1]?.split(/[/?#]/)[0];
      if (
        !/^https?:\/\//i.test(url) ||
        !authority ||
        authority.includes("@") ||
        parsed.username ||
        parsed.password ||
        url.includes("#") ||
        /[\s\\\u0000-\u001f\u007f]/.test(url) ||
        (parsed.port && !["80", "443"].includes(parsed.port)) ||
        url.length > 2048 ||
        parsed.href.length > 2048
      )
        throw new Error();
    } catch {
      nextErrors.url =
        "Enter an HTTP or HTTPS URL up to 2,048 characters, without credentials, fragments, or nonstandard ports.";
    }
    const number = (key: string, min: number, max: number) => {
      const raw = String(data.get(key) ?? "");
      const value = Number(raw);
      if (!raw || !Number.isInteger(value) || value < min || value > max)
        nextErrors[key] =
          `Enter a whole number from ${min.toLocaleString()} to ${max.toLocaleString()}.`;
      return value;
    };
    const body: MonitorCreate = {
      name,
      url,
      method: data.get("method") === "HEAD" ? "HEAD" : "GET",
      expected_status: number("expected_status", 200, 599),
      interval_seconds: number("interval_seconds", 60, 86400),
      timeout_seconds: number("timeout_seconds", 1, 10),
      enabled: data.get("enabled") === "on",
    };
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      setMessage("Check the highlighted fields and try again.");
      focusError();
      return;
    }
    setMessage("");
    mutation.mutate(body);
  }
  return (
    <>
      {!verified && <VerificationNotice />}
      <form
        noValidate
        aria-label={baseline ? "Edit monitor" : "Create monitor"}
        onSubmit={submit}
        className="max-w-2xl rounded-lg border border-border bg-surface p-5 sm:p-7"
      >
        {message && (
          <div
            ref={summary}
            role="alert"
            tabIndex={-1}
            className="mb-6 rounded-md border border-danger p-4 text-sm text-danger"
          >
            <p>{message}</p>
            {conflict && onReload && (
              <>
                <p className="mt-2">
                  Reloading will replace your unsaved edits.
                </p>
                <Button
                  className="mt-3"
                  variant="secondary"
                  loading={reloading}
                  onClick={onReload}
                >
                  Reload latest settings
                </Button>
              </>
            )}
            {mutation.error instanceof ApiError &&
              mutation.error.status === 0 && (
                <p className="mt-2">
                  The save may have reached the server. Check the monitor list
                  before submitting again.
                </p>
              )}
            {missing && (
              <Link className="mt-2 inline-block underline" href="/monitors">
                Back to monitors
              </Link>
            )}
          </div>
        )}
        <fieldset
          disabled={mutation.isPending || reloading}
          className="space-y-6"
        >
          <legend className="sr-only">Monitor configuration</legend>
          <TextField
            label="Monitor name"
            name="name"
            autoComplete="off"
            required
            maxLength={100}
            defaultValue={baseline?.name ?? ""}
            error={errors.name}
            placeholder="Payments API"
          />
          <TextField
            label="URL"
            name="url"
            type="url"
            autoComplete="off"
            spellCheck={false}
            required
            maxLength={2048}
            defaultValue={baseline?.url ?? ""}
            error={errors.url}
            placeholder="https://api.example.com/health"
            hint="HTTP or HTTPS on port 80 or 443. No credentials or fragments."
          />
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-2">
              <label
                htmlFor="monitor-method"
                className="block text-sm font-medium"
              >
                HTTP method
              </label>
              <select
                id="monitor-method"
                name="method"
                className="text-field"
                defaultValue={baseline?.method ?? "GET"}
              >
                <option value="GET">GET</option>
                <option value="HEAD">HEAD</option>
              </select>
            </div>
            <TextField
              label="Expected HTTP status"
              name="expected_status"
              type="number"
              min={200}
              max={599}
              step={1}
              required
              defaultValue={baseline?.expected_status ?? 200}
              error={errors.expected_status}
            />
            <TextField
              label="Check interval (seconds)"
              name="interval_seconds"
              type="number"
              min={60}
              max={86400}
              step={1}
              required
              defaultValue={baseline?.interval_seconds ?? 60}
              error={errors.interval_seconds}
              hint="60 to 86,400 seconds (one day)."
            />
            <TextField
              label="Timeout (seconds)"
              name="timeout_seconds"
              type="number"
              min={1}
              max={10}
              step={1}
              required
              defaultValue={baseline?.timeout_seconds ?? 5}
              error={errors.timeout_seconds}
              hint="1 to 10 seconds."
            />
          </div>
          <div className="rounded-md border border-border p-4">
            <label className="flex min-h-6 items-center gap-3 font-medium">
              <input
                type="checkbox"
                name="enabled"
                className="h-4 w-4 accent-accent"
                defaultChecked={baseline?.enabled ?? verified}
                disabled={!verified && !baseline?.enabled}
                aria-describedby="enabled-hint"
              />
              Enabled
            </label>
            <p id="enabled-hint" className="mt-2 text-xs text-muted">
              Save enabled to allow future scheduled checks, or leave this off
              to keep the monitor paused. Saving does not run a check.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 border-t border-border pt-6">
            <Button
              type="submit"
              loading={mutation.isPending}
              disabled={(!baseline && !verified) || conflict || missing}
            >
              {mutation.isPending
                ? "Saving…"
                : baseline
                  ? "Save changes"
                  : "Create monitor"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => router.push("/monitors")}
            >
              Cancel
            </Button>
          </div>
        </fieldset>
      </form>
    </>
  );
}
