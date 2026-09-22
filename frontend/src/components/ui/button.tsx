import type { ComponentPropsWithRef } from "react";

import { Icon } from "@/components/ui/icon";

type ButtonProps = ComponentPropsWithRef<"button"> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "default" | "icon";
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "default",
  loading = false,
  disabled,
  type = "button",
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`button button--${variant} ${size === "icon" ? "button--icon" : ""} ${className}`}
    >
      {loading && <Icon name="refresh" className="animate-spin" />}
      {children}
    </button>
  );
}
