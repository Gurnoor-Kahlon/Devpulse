import type { Metadata } from "next";
import { NotificationSettings } from "@/components/notifications/notification-settings";
export const metadata: Metadata = { title: "Notifications · DevPulse" };
export default function NotificationsPage() {
  return <NotificationSettings />;
}
