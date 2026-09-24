import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { MonitorEditor } from "@/components/monitors/monitor-editor";
export const metadata: Metadata = { title: "Edit monitor · DevPulse" };
export default async function EditMonitorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
  )
    notFound();
  return <MonitorEditor id={id} />;
}
