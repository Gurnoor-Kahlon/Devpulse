import type { Metadata } from "next";
import { DashboardView } from "@/components/dashboard/dashboard-view";

export const metadata: Metadata = { title: "Overview · DevPulse" };
export default function OverviewPage() {
  return <DashboardView />;
}
