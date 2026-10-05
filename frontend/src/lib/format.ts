export function formatUtc(value: string): string {
  return new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}
