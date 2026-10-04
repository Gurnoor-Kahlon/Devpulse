import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { User } from "@/lib/api/client";

export async function requireUser(): Promise<User> {
  const jar = await cookies();
  const cookie =
    jar.get("__Host-devpulse_session") ?? jar.get("devpulse_session");
  if (!cookie || !/^[A-Za-z0-9_-]{43}$/.test(cookie.value))
    redirect("/login?next=%2Fdashboard");
  let response: Response;
  try {
    const origin =
      process.env.DEVPULSE_CONTAINER_BUILD === "1"
        ? "http://api:8000"
        : "http://127.0.0.1:8000";
    response = await fetch(`${origin}/api/v1/auth/me`, {
      headers: { Cookie: `${cookie.name}=${cookie.value}` },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(7_000),
    });
  } catch {
    throw new Error("Account service is unavailable.");
  }
  if (response.status === 401)
    redirect("/login?reason=expired&next=%2Fdashboard");
  if (!response.ok) throw new Error("Account service is unavailable.");
  return response.json() as Promise<User>;
}
