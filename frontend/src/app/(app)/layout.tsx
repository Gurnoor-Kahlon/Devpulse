import type { ReactNode } from "react";

import { ApplicationShell } from "@/components/shell/application-shell";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return <ApplicationShell>{children}</ApplicationShell>;
}
