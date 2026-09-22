"use client";

import { useEffect, useState } from "react";

import { WorkspaceNavigation } from "@/components/shell/workspace-navigation";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";

export function MobileNavigation() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) setOpen(false);
    };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation"
          className="md:hidden"
        >
          <Icon name="menu" />
        </Button>
      </DialogTrigger>
      <DialogContent
        title="DevPulse"
        description="Reliability at a glance."
        variant="drawer"
        onCloseAutoFocus={(event) => {
          if (window.matchMedia("(min-width: 768px)").matches) {
            event.preventDefault();
            document.getElementById("main-content")?.focus();
          }
        }}
      >
        <WorkspaceNavigation onNavigate={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
