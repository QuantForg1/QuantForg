import { AuthLayoutProviders } from "@/providers/auth-layout-providers";

export default function AuthGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthLayoutProviders>{children}</AuthLayoutProviders>;
}
