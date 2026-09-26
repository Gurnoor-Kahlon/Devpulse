import type { Metadata } from "next";
import { IncidentDetailView } from "@/components/incidents/incident-detail";
export const metadata: Metadata = { title: "Incident · DevPulse" };
export default async function IncidentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <IncidentDetailView id={id} />;
}
