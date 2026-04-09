import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { DashboardSessionShell } from "@/components/dashboard-session-shell";
import { LogoutButton } from "@/components/logout-button";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardSessionShell>
      <div className="brand-shell min-h-screen px-6 py-6">
        <div className="relative mx-auto max-w-7xl">
          <header className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-brand-200 bg-white/85 px-5 py-4 shadow-panel backdrop-blur-sm">
            <BrandMark compact showSlogan={false} />
            <nav className="flex flex-wrap items-center gap-2 text-sm">
              <Link href="/sessions" className="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-ink hover:bg-brand-50">
                Sesiones
              </Link>
              <Link href="/profile" className="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-ink hover:bg-brand-50">
                Perfil
              </Link>
              <LogoutButton className="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-ink hover:bg-brand-50" />
            </nav>
          </header>

          {children}
        </div>
      </div>
    </DashboardSessionShell>
  );
}
