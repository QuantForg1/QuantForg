import { AppShell } from "@/components/layout/app-shell";
import { AuthLayoutProviders } from "@/providers/auth-layout-providers";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthLayoutProviders>
      <AppShell>{children}</AppShell>
    </AuthLayoutProviders>
  );
}
