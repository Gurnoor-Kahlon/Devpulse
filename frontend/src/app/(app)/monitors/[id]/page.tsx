import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { MonitorDetail } from "@/components/monitors/monitor-detail";
export const metadata: Metadata = { title: "Monitor history · DevPulse" };
export default async function MonitorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
  )
    notFound();
  return <MonitorDetail id={id} />;
}
