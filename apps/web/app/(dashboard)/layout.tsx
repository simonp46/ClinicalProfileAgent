import Link from "next/link";

import { AppFooter } from "@/components/app-footer";
import { BrandMark } from "@/components/brand-mark";
import { DashboardSessionShell } from "@/components/dashboard-session-shell";
import { ProfileMenu } from "@/components/profile-menu";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardSessionShell>
      <div className="brand-shell min-h-screen px-3 py-4 sm:px-4 sm:py-6 lg:px-6">
        <div className="relative mx-auto flex min-h-[calc(100vh-2rem)] max-w-7xl flex-col sm:min-h-[calc(100vh-3rem)]">
          <header className="mb-4 rounded-3xl border border-brand-200 bg-white/85 px-4 py-4 shadow-panel backdrop-blur-sm sm:mb-5 sm:px-5">
            <div className="flex items-center justify-between gap-4">
              <Link
                href="/sessions"
                aria-label="Ir a sesiones"
                className="inline-flex rounded-2xl outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <BrandMark compact showSlogan={false} />
              </Link>

              <div className="flex justify-end lg:flex-none">
                <ProfileMenu />
              </div>
            </div>
          </header>

          <div className="flex-1">{children}</div>

          <AppFooter />
        </div>
      </div>
    </DashboardSessionShell>
  );
}
