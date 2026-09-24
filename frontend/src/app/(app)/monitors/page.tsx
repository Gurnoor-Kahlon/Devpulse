import type { Metadata } from "next";
import { MonitorList } from "@/components/monitors/monitor-list";
export const metadata: Metadata = { title: "Monitors · DevPulse" };
export default function MonitorsPage() {
  return <MonitorList />;
}
