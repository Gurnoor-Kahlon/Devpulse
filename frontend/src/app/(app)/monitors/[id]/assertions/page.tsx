import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AssertionEditor } from "@/components/monitors/assertion-editor";
export const metadata: Metadata = { title: "Response assertions · DevPulse" };
export default async function AssertionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
  )
    notFound();
  return <AssertionEditor id={id} />;
}
