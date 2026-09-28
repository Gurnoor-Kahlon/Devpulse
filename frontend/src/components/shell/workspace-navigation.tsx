"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon } from "@/components/ui/icon";

export function WorkspaceNavigation({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label="Workspace">
      <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-muted uppercase">
        Workspace
      </p>
      <Link
        href="/dashboard"
        aria-current={pathname === "/dashboard" ? "page" : undefined}
        onClick={onNavigate}
        className="nav-link"
      >
        <Icon name="overview" />
        Overview
      </Link>
      <Link
        href="/monitors"
        aria-current={pathname.startsWith("/monitors") ? "page" : undefined}
        onClick={onNavigate}
        className="nav-link mt-2"
      >
        <Icon name="pulse" /> Monitors
      </Link>
      <Link
        href="/incidents"
        aria-current={pathname.startsWith("/incidents") ? "page" : undefined}
        onClick={onNavigate}
        className="nav-link mt-2"
      >
        <Icon name="alert" /> Incidents
      </Link>
      <Link
        href="/notifications"
        aria-current={pathname === "/notifications" ? "page" : undefined}
        onClick={onNavigate}
        className="nav-link mt-2"
      >
        <Icon name="mail" /> Notifications
      </Link>
    </nav>
  );
}
