"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { ApiError, authPost } from "@/lib/api/client";
import { goToWorkspace } from "@/lib/auth/redirect";

export type AuthMode =
  "login" | "register" | "verify" | "resend" | "forgot" | "reset";
const content = {
  login: {
    title: "Welcome back",
    description: "Sign in to your DevPulse workspace.",
    button: "Sign in",
    pending: "Signing in…",
  },
  register: {
    title: "Create your account",
    description:
      "Start with an account. Verify your email to get ready for monitoring.",
    button: "Create account",
    pending: "Creating account…",
  },
  verify: {
    title: "Verify your email",
    description:
      "Enter the verification code from your email. It’s valid for 24 hours.",
    button: "Verify email",
    pending: "Verifying…",
  },
  resend: {
    title: "Request a new code",
    description:
      "Enter your account email to request a fresh verification code.",
    button: "Send verification code",
    pending: "Sending…",
  },
  forgot: {
    title: "Recover your account",
    description:
      "We’ll email a single-use code if this address has an account.",
    button: "Send reset code",
    pending: "Sending…",
  },
  reset: {
    title: "Choose a new password",
    description:
      "Enter the reset code from your email. It’s valid for 30 minutes.",
    button: "Reset password",
    pending: "Resetting…",
  },
} as const;
const successContent = {
  register: {
    message:
      "If this request is eligible, an email will arrive shortly. Enter its code to verify your email.",
    href: "/verify-email",
    label: "Enter verification code",
  },
  verify: {
    message: "Your email is verified. You can now sign in to your account.",
    href: "/login",
    label: "Continue to sign in",
  },
  resend: {
    message:
      "If this request is eligible, an email will arrive shortly. Use the newest code; older codes no longer work.",
    href: "/verify-email",
    label: "Enter verification code",
  },
  forgot: {
    message:
      "If this request is eligible, an email will arrive shortly. Use its code to choose a new password.",
    href: "/reset-password",
    label: "Enter reset code",
  },
  reset: {
    message:
      "Your password has been reset and existing sessions have been signed out. Sign in with your new password.",
    href: "/login",
    label: "Continue to sign in",
  },
} as const;

export function AuthForm({
  mode,
  returnTo = "/dashboard",
  notice,
}: {
  mode: AuthMode;
  returnTo?: string;
  notice?: string;
}) {
  const form = useRef<HTMLFormElement>(null);
  const summary = useRef<HTMLParagraphElement>(null);
  const successMessage = useRef<HTMLDivElement>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const cache = useQueryClient();
  const hasEmail = ["login", "register", "resend", "forgot"].includes(mode);
  const hasPassword = ["login", "register", "reset"].includes(mode);
  const newPassword = mode === "register" || mode === "reset";
  const hasCode = mode === "verify" || mode === "reset";
  const copy = content[mode];
  const focusError = () =>
    requestAnimationFrame(() => summary.current?.focus());
  const mutation = useMutation({
    // Mutation variables never retain credentials: read the form only during execution.
    mutationFn: async () => {
      const fields = new FormData(form.current!);
      const email = String(fields.get("email") ?? "").trim();
      const password = String(fields.get("password") ?? "");
      const token = String(fields.get("token") ?? "").trim();
      switch (mode) {
        case "login":
          return authPost("/api/v1/auth/login", { email, password });
        case "register":
          return authPost("/api/v1/auth/register", { email, password });
        case "verify":
          return authPost("/api/v1/auth/verify-email", { token });
        case "resend":
          return authPost("/api/v1/auth/resend-verification", { email });
        case "forgot":
          return authPost("/api/v1/auth/forgot-password", { email });
        case "reset":
          return authPost("/api/v1/auth/reset-password", { token, password });
      }
    },
    onSuccess: () => {
      form.current?.reset();
      if (mode === "login") {
        cache.clear();
        goToWorkspace(returnTo);
      } else {
        if (mode === "reset") cache.clear();
        if (mode === "verify")
          void cache.invalidateQueries({ queryKey: ["session"] });
        requestAnimationFrame(() => successMessage.current?.focus());
      }
    },
    onError: (error) => {
      const fieldErrors: Record<string, string> = {};
      if (error instanceof ApiError) {
        for (const field of error.fields ?? []) {
          const name = field.field.split(".").at(-1) ?? "";
          if (["email", "password", "token"].includes(name))
            fieldErrors[name] = "Check this value and try again.";
        }
      }
      setErrors(fieldErrors);
      focusError();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    mutation.reset();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const token = String(data.get("token") ?? "").trim();
    const nextErrors: Record<string, string> = {};
    if (
      hasEmail &&
      (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254)
    )
      nextErrors.email = "Enter a valid email address.";
    if (
      hasPassword &&
      ([...password].length < (newPassword ? 12 : 1) ||
        [...password].length > 128)
    )
      nextErrors.password = newPassword
        ? "Use 12–128 characters."
        : "Enter your password (up to 128 characters).";
    if (newPassword && String(data.get("confirmation")) !== password)
      nextErrors.confirmation = "The passwords don’t match.";
    if (hasCode && !/^[A-Za-z0-9_-]{43}$/.test(token))
      nextErrors.token = "Copy the complete 43-character code from your email.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      focusError();
      return;
    }
    mutation.mutate();
  }
  const success =
    mutation.isSuccess && mode !== "login" ? successContent[mode] : null;
  return (
    <>
      <p className="mb-3 text-xs font-semibold tracking-widest text-accent uppercase">
        Your workspace
      </p>
      <h1 className="text-3xl font-semibold tracking-tight">{copy.title}</h1>
      <p className="mt-3 text-sm text-muted">{copy.description}</p>
      {notice && (
        <p
          role="status"
          className="mt-5 rounded-md border border-border p-3 text-sm text-muted"
        >
          {notice}
        </p>
      )}
      {success ? (
        <div
          ref={successMessage}
          tabIndex={-1}
          className="mt-7 space-y-5 outline-none"
        >
          <p
            role="status"
            className="rounded-md border border-border bg-elevated p-4"
          >
            {success.message}
          </p>
          <Link href={success.href} className="button button--primary w-full">
            {success.label}
          </Link>
          {mode === "verify" && (
            <Link
              href="/dashboard"
              className="block text-center text-sm text-accent underline underline-offset-4"
            >
              Back to workspace
            </Link>
          )}
        </div>
      ) : (
        <form
          ref={form}
          onSubmit={submit}
          noValidate
          className="mt-7 space-y-5"
          aria-label={copy.title}
        >
          {(Object.keys(errors).length > 0 || mutation.isError) && (
            <p
              ref={summary}
              role="alert"
              tabIndex={-1}
              className="rounded-md border border-danger p-3 text-sm text-danger"
            >
              {mutation.error instanceof ApiError
                ? mutation.error.message
                : mutation.isError
                  ? "Something went wrong. Please try again."
                  : "Check the highlighted fields and try again."}
            </p>
          )}
          {hasEmail && (
            <TextField
              label="Email address"
              name="email"
              type="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              required
              error={errors.email}
              readOnly={mutation.isPending}
            />
          )}
          {hasCode && (
            <TextField
              label={mode === "verify" ? "Verification code" : "Reset code"}
              name="token"
              autoComplete="one-time-code"
              autoCapitalize="none"
              spellCheck={false}
              required
              error={errors.token}
              readOnly={mutation.isPending}
              className="font-mono text-xs"
            />
          )}
          {hasPassword && (
            <TextField
              label={mode === "reset" ? "New password" : "Password"}
              name="password"
              type="password"
              autoComplete={newPassword ? "new-password" : "current-password"}
              required
              hint={
                newPassword
                  ? "Use 12–128 characters. Spaces are preserved."
                  : undefined
              }
              error={errors.password}
              readOnly={mutation.isPending}
            />
          )}
          {newPassword && (
            <TextField
              label="Confirm password"
              name="confirmation"
              type="password"
              autoComplete="new-password"
              required
              error={errors.confirmation}
              readOnly={mutation.isPending}
            />
          )}
          <Button type="submit" loading={mutation.isPending} className="w-full">
            {mutation.isPending ? copy.pending : copy.button}
          </Button>
        </form>
      )}
      <nav
        aria-label="Account access"
        className="mt-7 flex flex-wrap justify-center gap-x-5 gap-y-3 border-t border-border pt-6 text-sm text-accent [&_a]:underline [&_a]:underline-offset-4"
      >
        {mode === "login" ? (
          <>
            <Link href="/register">Create an account</Link>
            <Link href="/forgot-password">Forgot password?</Link>
          </>
        ) : (
          <Link href="/login">Sign in</Link>
        )}
        {mode === "verify" && (
          <Link href="/resend-verification">Request a new code</Link>
        )}
        {mode === "reset" && (
          <Link href="/forgot-password">Request a new reset code</Link>
        )}
        {mode === "resend" && (
          <Link href="/verify-email">Enter verification code</Link>
        )}
      </nav>
    </>
  );
}
