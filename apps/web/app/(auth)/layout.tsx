import { BrandMark } from "@/components/brand-mark";
import { AppFooter } from "@/components/app-footer";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="brand-shell min-h-screen px-4 py-6 sm:px-6 sm:py-8">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl flex-col">
        <div className="relative flex flex-1 items-center">
          <div className="grid w-full items-center gap-8 lg:grid-cols-[1.15fr_1fr]">
            <section className="rounded-3xl border border-brand-200 bg-white/75 p-6 shadow-panel backdrop-blur-sm sm:p-8">
              <BrandMark />
              <p className="mt-6 max-w-xl text-sm text-ink/85">
                Plataforma interna para documentacion clinica asistida. Los borradores requieren revision y validacion
                profesional antes de su uso.
              </p>
            </section>

            <section className="relative flex justify-center lg:justify-end">{children}</section>
          </div>
        </div>

        <AppFooter />
      </div>
    </div>
  );
}
