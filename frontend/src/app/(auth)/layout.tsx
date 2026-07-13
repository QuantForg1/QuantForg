import { AuthFormProviders } from "@/providers/auth-form-providers";

export default function AuthGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthFormProviders>{children}</AuthFormProviders>;
}
