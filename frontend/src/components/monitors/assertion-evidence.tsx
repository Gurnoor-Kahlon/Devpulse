import type { AssertionResult } from "@/lib/api/monitors";

const reasons: Record<AssertionResult["reason"], string> = {
  matched: "Matched",
  text_not_found: "Text not found",
  pointer_missing: "JSON Pointer not found",
  value_mismatch: "Value or type did not match",
  invalid_json: "Invalid JSON response",
  invalid_utf8: "Response is not valid UTF-8",
  evaluation_limit: "JSON evaluation limit exceeded",
  response_unavailable: "Complete response unavailable",
};

export function AssertionEvidence({ results }: { results: AssertionResult[] }) {
  return (
    <section aria-label="Assertion evidence" className="mt-4 space-y-3 text-sm">
      <h3 className="font-medium">Assertion evidence</h3>
      {results.length === 0 ? (
        <p className="text-muted">
          No assertion snapshots recorded for this attempt.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted">
            Definitions captured for this attempt. Actual response values are
            not retained.
          </p>
          <ul className="space-y-3">
            {results.map((result) => (
              <li
                key={result.definition.id}
                className="min-w-0 rounded border border-border p-3"
              >
                <p className="font-medium">
                  {result.status === "passed"
                    ? "Passed"
                    : result.status === "failed"
                      ? "Failed"
                      : "Not evaluated"}{" "}
                  · {reasons[result.reason]}
                </p>
                <p className="mt-1 break-all">
                  {result.definition.kind === "text_contains"
                    ? "Text contains"
                    : `JSON equals at ${result.definition.pointer || "(root)"}`}
                </p>
                <p className="mt-1 break-all font-mono">
                  Expected: {JSON.stringify(result.definition.expected)}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
