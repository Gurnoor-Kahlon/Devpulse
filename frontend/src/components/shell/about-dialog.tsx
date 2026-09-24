"use client";

import type { ReactElement } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";

export function AboutDialog({ trigger }: { trigger: ReactElement }) {
  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        title="About DevPulse"
        description="Reliability at a glance. A workspace for API monitoring and incident history."
      >
        <p className="text-sm leading-6 text-muted">
          You can save and manage monitor configurations. Health checks are not
          running yet. Your overview will show real results once monitoring is
          connected.
        </p>
        <DialogClose asChild>
          <Button className="mt-6">Got it</Button>
        </DialogClose>
      </DialogContent>
    </Dialog>
  );
}
