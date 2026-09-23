import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
export const metadata: Metadata = { title: "New verification code · DevPulse" };
export default function ResendPage() {
  return <AuthForm mode="resend" />;
}
