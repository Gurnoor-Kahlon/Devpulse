// Extend this allowlist only when another protected destination is implemented.
export function safeReturnPath(value: unknown): string {
  const allowed = new Set([
    "/dashboard",
    "/monitors",
    "/monitors/new",
    "/incidents",
  ]);
  if (
    typeof value === "string" &&
    (/^\/incidents\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value,
    ) ||
      /^\/monitors\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\/edit)?$/i.test(
        value,
      ))
  )
    return value;
  return typeof value === "string" && allowed.has(value) ? value : "/dashboard";
}

export function goToWorkspace(value: unknown) {
  window.location.replace(safeReturnPath(value));
}
export function leaveWorkspace(reason: "expired" | "signed-out") {
  window.location.replace(`/login?reason=${reason}&next=%2Fdashboard`);
}
