import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/app-shell";
export const metadata: Metadata = {
  title: { default: "Knowledge Engine", template: "%s · Knowledge Engine" },
  description:
    "Tenant-scoped knowledge, grounded answers and inspectable evidence.",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
