import { request } from "./client";
import type { components } from "./schema";
export type Demo = components["schemas"]["DemoResponse"];
export type DemoWindow = components["schemas"]["RunHistory"]["window"];
export function getDemo(
  window: DemoWindow,
  signal?: AbortSignal,
): Promise<Demo> {
  return request<Demo>(`/api/v1/demo?${new URLSearchParams({ window })}`, {
    signal,
  });
}
