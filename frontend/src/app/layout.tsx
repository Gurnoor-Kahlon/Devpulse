import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { QueryProvider } from "@/components/auth/query-provider";

export const metadata: Metadata = {
  title: "DevPulse",
  description: "Reliability at a glance.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
