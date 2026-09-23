// Extend this allowlist only when another protected destination is implemented.
export function safeReturnPath(value: unknown): string {
  const allowed = new Set(["/dashboard"]);
  return typeof value === "string" && allowed.has(value) ? value : "/dashboard";
}

export function goToWorkspace(value: unknown) {
  window.location.replace(safeReturnPath(value));
}
export function leaveWorkspace(reason: "expired" | "signed-out") {
  window.location.replace(`/login?reason=${reason}&next=%2Fdashboard`);
}
