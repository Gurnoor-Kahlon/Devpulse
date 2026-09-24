import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import OverviewPage from "@/app/(app)/dashboard/page";
import { ApplicationShell } from "@/components/shell/application-shell";
import { MobileNavigation } from "@/components/shell/mobile-navigation";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import {
  StatusIndicator,
  type MonitorStatus,
} from "@/components/ui/status-indicator";

describe("Application shell", () => {
  it("provides a focusable skip target and navigation only to implemented destinations", () => {
    render(
      <ApplicationShell>
        <OverviewPage />
      </ApplicationShell>,
    );
    const main = screen.getByRole("main");
    expect(
      screen.getByRole("link", { name: "Skip to content" }),
    ).toHaveAttribute("href", `#${main.id}`);
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    for (const link of screen.getAllByRole("link")) {
      expect(["/dashboard", "/monitors", "#main-content"]).toContain(
        link.getAttribute("href"),
      );
    }
    expect(
      screen.getByRole("heading", { level: 1, name: "Overview" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No monitoring data yet")).toBeInTheDocument();
    expect(screen.queryByText(/\d+%|\d+\s*ms/)).not.toBeInTheDocument();
  });

  it("closes the mobile drawer when its navigation link is selected", async () => {
    const user = userEvent.setup();
    render(<MobileNavigation />);
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(
      screen.getByRole("dialog", { name: "DevPulse" }),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Overview" });
    // Keep jsdom on this document while exercising the real link click handler.
    link.addEventListener("click", (event) => event.preventDefault());
    fireEvent.click(link);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("returns focus to the menu trigger when Escape dismisses mobile navigation", async () => {
    const user = userEvent.setup();
    render(<MobileNavigation />);
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
  });
});

describe("Feedback states", () => {
  it("announces loading once without exposing decorative skeletons", () => {
    render(<LoadingState label="Loading monitor history" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading monitor history",
    );
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("renders an empty state without inventing an action", () => {
    render(
      <EmptyState
        title="No history yet"
        description="History will appear after checks run."
      />,
    );
    expect(
      screen.getByRole("heading", { name: "No history yet" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("announces failure and invokes the supplied recovery action", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(<ErrorState onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This view couldn't be loaded",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("distinguishes monitor states with text rather than color alone", () => {
    const statuses: MonitorStatus[] = [
      "operational",
      "confirming",
      "failing",
      "paused",
      "unknown",
    ];
    render(
      <>
        {statuses.map((status) => (
          <StatusIndicator key={status} status={status} />
        ))}
      </>,
    );
    for (const label of [
      "Operational",
      "Confirming failure",
      "Failing",
      "Paused",
      "No data",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });
});
