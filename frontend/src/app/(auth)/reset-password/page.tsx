import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
export const metadata: Metadata = { title: "Reset password · DevPulse" };
export default function ResetPage() {
  return <AuthForm mode="reset" />;
}
