import type { Metadata } from "next";
import { MonitorForm } from "@/components/monitors/monitor-form";
import { MonitorHeading } from "@/components/monitors/monitor-heading";
export const metadata: Metadata = { title: "Create monitor · DevPulse" };
export default function NewMonitorPage() {
  return (
    <>
      <MonitorHeading title="Create monitor" />
      <MonitorForm />
    </>
  );
}
