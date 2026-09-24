"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentProps } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

type DialogContentProps = ComponentProps<typeof DialogPrimitive.Content> & {
  title: string;
  description: string;
  variant?: "dialog" | "drawer";
  closeDisabled?: boolean;
};

export function DialogContent({
  title,
  description,
  variant = "dialog",
  closeDisabled = false,
  children,
  className = "",
  ...props
}: DialogContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="dialog-overlay" />
      <DialogPrimitive.Content
        {...props}
        className={`dialog-content ${variant === "drawer" ? "dialog-content--drawer" : ""} ${className}`}
      >
        <DialogPrimitive.Title className="pr-10 text-lg font-semibold tracking-tight">
          {title}
        </DialogPrimitive.Title>
        <DialogPrimitive.Description className="mt-2 pr-4 text-sm text-muted">
          {description}
        </DialogPrimitive.Description>
        {children && <div className="mt-6">{children}</div>}
        <DialogPrimitive.Close asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Close dialog"
            disabled={closeDisabled}
            className="absolute top-3 right-3"
          >
            <Icon name="close" />
          </Button>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
