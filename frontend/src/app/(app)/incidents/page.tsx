import type { Metadata } from "next";
import { IncidentList } from "@/components/incidents/incident-list";
export const metadata: Metadata = { title: "Incidents · DevPulse" };
export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<{ monitor?: string }>;
}) {
  const { monitor } = await searchParams;
  return <IncidentList key={monitor ?? "all"} monitorId={monitor} />;
}
