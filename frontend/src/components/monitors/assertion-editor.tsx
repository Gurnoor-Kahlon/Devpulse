"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiError } from "@/lib/api/client";
import {
  getAssertions,
  replaceAssertions,
  type AssertionPage,
  type AssertionDefinition,
} from "@/lib/api/monitors";
import { MonitorHeading } from "./monitor-heading";

type Draft = {
  key: number;
  kind: AssertionDefinition["kind"];
  pointer: string;
  value: string;
};

function AssertionForm({
  page,
  onReload,
  reloading,
}: {
  page: AssertionPage;
  onReload: () => void;
  reloading: boolean;
}) {
  const cache = useQueryClient();
  const [items, setItems] = useState<Draft[]>(() =>
    page.items.map((item, key) => ({
      key,
      kind: item.kind,
      pointer: item.pointer ?? "",
      value:
        item.kind === "text_contains"
          ? String(item.expected)
          : JSON.stringify(item.expected),
    })),
  );
  const [nextKey, setNextKey] = useState(page.items.length);
  const [version, setVersion] = useState(page.configuration_version);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const update = (key: number, changes: Partial<Draft>) => {
    setMessage("");
    setItems((rows) =>
      rows.map((row) => (row.key === key ? { ...row, ...changes } : row)),
    );
  };
  return (
    <form
      className="max-w-2xl space-y-5"
      onSubmit={async (event) => {
        event.preventDefault();
        setError("");
        setMessage("");
        let definitions: AssertionDefinition[];
        try {
          definitions = items.map((item) => {
            const expected: unknown =
              item.kind === "text_contains"
                ? item.value
                : JSON.parse(item.value);
            if (
              expected !== null &&
              !["string", "number", "boolean"].includes(typeof expected)
            )
              throw new Error();
            if (
              typeof expected === "number" &&
              (!Number.isFinite(expected) ||
                Math.abs(expected) > Number.MAX_SAFE_INTEGER)
            )
              throw new Error();
            if (
              typeof expected === "string" &&
              (expected.length > 1024 ||
                expected.includes("\0") ||
                (item.kind === "text_contains" && !expected))
            )
              throw new Error();
            return {
              kind: item.kind,
              pointer: item.kind === "json_equals" ? item.pointer : "",
              expected: expected as AssertionDefinition["expected"],
            };
          });
        } catch {
          setError(
            "Use non-empty text or a valid JSON scalar: a quoted string, number, true, false, or null. Strings are limited to 1,024 characters; numbers must be finite and within ±9,007,199,254,740,991.",
          );
          return;
        }
        setSaving(true);
        try {
          const saved = await replaceAssertions(page.monitor_id, {
            configuration_version: version,
            items: definitions,
          });
          setVersion(saved.configuration_version);
          setConflict(false);
          setMessage(
            "Assertions saved. Future checks will use these definitions.",
          );
          void cache.invalidateQueries({
            queryKey: ["monitor", page.monitor_id],
          });
          void cache.invalidateQueries({
            queryKey: ["monitor-analytics", page.monitor_id],
          });
          void cache.invalidateQueries({ queryKey: ["monitors"] });
        } catch (cause) {
          const stale = cause instanceof ApiError && cause.status === 409;
          setConflict(stale);
          setError(
            stale
              ? "Monitor settings changed. Your edits are preserved. Reload saved assertions before trying again."
              : cause instanceof ApiError && cause.status === 422
                ? "Could not save. Check the JSON Pointer syntax, string limits, and monitor method. Body assertions require GET."
                : cause instanceof ApiError && cause.status === 404
                  ? "This monitor is unavailable. It may have been archived."
                  : "Could not confirm the save. Your edits are preserved. Reload to check the saved state before trying again.",
          );
        } finally {
          setSaving(false);
        }
      }}
    >
      <p className="text-sm text-muted">
        Up to 10 assertions; all must pass alongside the expected HTTP status.
        Failures use the existing retry and incident rules. Configuration v
        {version} · {page.method}.
      </p>
      <p className="text-sm text-muted">
        Configured expected values are saved in check and incident evidence.
        Actual response values and response bodies are not retained. Avoid
        putting secrets in expected values.
      </p>
      {page.method === "HEAD" && (
        <p role="status" className="text-sm text-muted">
          Body assertions require GET. Change the monitor method in settings
          first.
        </p>
      )}
      {items.length === 0 && (
        <p>
          No response assertions configured. Checks use the expected HTTP
          status.
        </p>
      )}
      <fieldset disabled={saving || reloading} className="space-y-4">
        <legend className="sr-only">Assertion definitions</legend>
        {items.map((item, index) => (
          <fieldset
            key={item.key}
            className="space-y-3 rounded-lg border border-border bg-surface p-5"
          >
            <legend className="px-1 font-semibold">
              Assertion {index + 1}
            </legend>
            <label className="block text-sm">
              Type
              <select
                className="text-field mt-2"
                value={item.kind}
                onChange={(event) =>
                  update(item.key, {
                    kind: event.target.value as Draft["kind"],
                    value: "",
                    pointer: "",
                  })
                }
              >
                <option value="json_equals">JSON Pointer equals</option>
                <option value="text_contains">Text contains</option>
              </select>
            </label>
            {item.kind === "json_equals" && (
              <label className="block text-sm">
                JSON Pointer
                <input
                  className="text-field mt-2"
                  maxLength={512}
                  value={item.pointer}
                  onChange={(event) =>
                    update(item.key, { pointer: event.target.value })
                  }
                  aria-describedby={`pointer-help-${item.key}`}
                />
                <span
                  id={`pointer-help-${item.key}`}
                  className="mt-2 block text-xs text-muted"
                >
                  Empty selects the root. Example: /health/ok. Escape ~ as ~0
                  and / as ~1. At most 32 segments.
                </span>
              </label>
            )}
            <label className="block text-sm">
              {item.kind === "text_contains"
                ? "Expected text"
                : "Expected JSON value"}
              <textarea
                className="text-field mt-2 min-h-20 font-mono"
                required
                maxLength={8192}
                value={item.value}
                onChange={(event) =>
                  update(item.key, { value: event.target.value })
                }
                aria-describedby={`value-help-${item.key}`}
              />
              <span
                id={`value-help-${item.key}`}
                className="mt-2 block text-xs text-muted"
              >
                {item.kind === "text_contains"
                  ? "Case-sensitive UTF-8 text, up to 1,024 characters."
                  : 'A scalar only: true, false, null, 42, or "healthy". Types must match; 1 differs from true and "1".'}
              </span>
            </label>
            <Button
              variant="ghost"
              onClick={() => {
                setMessage("");
                setItems((rows) => rows.filter((row) => row.key !== item.key));
              }}
            >
              Remove assertion {index + 1}
            </Button>
          </fieldset>
        ))}
        <Button
          variant="secondary"
          disabled={items.length >= 10 || page.method === "HEAD"}
          onClick={() => {
            setMessage("");
            setItems((rows) => [
              ...rows,
              { key: nextKey, kind: "json_equals", pointer: "", value: "" },
            ]);
            setNextKey(nextKey + 1);
          }}
        >
          Add assertion
        </Button>
      </fieldset>
      <p className="text-xs text-muted">
        Evaluation accepts at most 1 MiB of response data, 32 JSON nesting
        levels, and 10,000 structural separators. Malformed or over-limit JSON
        fails JSON assertions. Text assertions do not require JSON.
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
          Save assertions
        </Button>
        <Button
          variant="secondary"
          disabled={saving}
          loading={reloading}
          onClick={onReload}
        >
          Reload saved assertions
        </Button>
      </div>
      <p className="text-xs text-muted">
        Reload replaces your unsaved edits with the saved definitions.
      </p>
    </form>
  );
}

export function AssertionEditor({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["assertions", id],
    queryFn: ({ signal }) => getAssertions(id, signal),
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  return (
    <>
      <MonitorHeading title="Response assertions">
        <Link href={`/monitors/${id}`} className="button button--secondary">
          Monitor history
        </Link>
      </MonitorHeading>
      <Link
        href={`/monitors/${id}/edit`}
        className="mb-5 inline-block text-sm underline"
      >
        Edit monitor settings
      </Link>
      {query.isPending ? (
        <LoadingState label="Loading assertions" />
      ) : query.error instanceof ApiError && query.error.status === 404 ? (
        <p role="alert">
          This monitor is unavailable. It may have been archived.
        </p>
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Could not reload assertions. Your edits are preserved.
            </p>
          )}
          <AssertionForm
            key={query.dataUpdatedAt}
            page={query.data}
            onReload={() => void query.refetch()}
            reloading={query.isFetching}
          />
        </>
      )}
    </>
  );
}
