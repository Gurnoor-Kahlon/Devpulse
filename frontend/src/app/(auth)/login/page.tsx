import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
import { safeReturnPath } from "@/lib/auth/redirect";
export const metadata: Metadata = { title: "Sign in · DevPulse" };
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const notice =
    params.reason === "expired"
      ? "Your session has expired. Sign in to continue."
      : params.reason === "signed-out"
        ? "You’ve been signed out."
        : undefined;
  return (
    <AuthForm
      mode="login"
      returnTo={safeReturnPath(params.next)}
      notice={notice}
    />
  );
}
