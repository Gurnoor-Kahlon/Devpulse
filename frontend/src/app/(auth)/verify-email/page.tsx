import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
export const metadata: Metadata = { title: "Verify email · DevPulse" };
export default function VerifyPage() {
  return <AuthForm mode="verify" />;
}
