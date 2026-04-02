import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { fetchServerProfile } from "@/lib/server-profile";

type AdminLayoutProps = {
  children: ReactNode;
};

export default async function AdminLayout({ children }: AdminLayoutProps) {
  const locale = await getLocale();
  const profile = await fetchServerProfile();
  if (!profile) {
    redirect(`/${locale}/login`);
  }
  if (!profile.is_admin) {
    redirect(`/${locale}/upload`);
  }

  return (
    <AppShell>
      <div className="w-full px-2">
        <h1
          className="font-heading text-2xl mb-2"
          style={{ color: "var(--color-navy)" }}
        >
          Admin
        </h1>
        <p className="text-sm mb-8" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
          Signed in as {profile.email}
        </p>
        {children}
      </div>
    </AppShell>
  );
}
