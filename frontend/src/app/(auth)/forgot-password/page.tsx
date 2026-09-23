import type { Metadata } from "next";
import { AuthForm } from "@/components/auth/auth-form";
export const metadata: Metadata = { title: "Recover account · DevPulse" };
export default function ForgotPage() {
  return <AuthForm mode="forgot" />;
}
