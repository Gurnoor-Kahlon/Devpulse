import type { ReactNode } from "react";

import { SessionGate } from "@/components/auth/session-gate";
import { requireUser } from "@/lib/auth/server";

export default async function WorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await requireUser();
  return <SessionGate initialUser={user}>{children}</SessionGate>;
}
