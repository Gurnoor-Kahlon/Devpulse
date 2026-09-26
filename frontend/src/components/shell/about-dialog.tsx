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
          Enabled monitors are eligible for scheduled checks. Observations can
          become stale when checks are delayed. Health evaluation and incident
          history are not available yet.
        </p>
        <DialogClose asChild>
          <Button className="mt-6">Got it</Button>
        </DialogClose>
      </DialogContent>
    </Dialog>
  );
}
