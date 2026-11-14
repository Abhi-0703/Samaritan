import { AppShell } from "@/components/app-shell";

// The dashboard (Overview, Calls, Agents, Rules, Accuracy) lives in this group, so only these pages get the sidebar.
// The landing page (/) and the upload-and-analyse page (/try) sit outside it.
export default function DashboardLayout({ children }: LayoutProps<"/">) {
  return <AppShell>{children}</AppShell>;
}
