import Link from "next/link";

import { Icon } from "@/components/ui/icon";

export function WorkspaceNavigation({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Workspace">
      <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-muted uppercase">
        Workspace
      </p>
      <Link
        href="/dashboard"
        aria-current="page"
        onClick={onNavigate}
        className="nav-link"
      >
        <Icon name="overview" />
        Overview
      </Link>
    </nav>
  );
}
