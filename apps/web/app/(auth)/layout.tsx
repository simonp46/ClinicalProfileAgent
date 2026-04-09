import { BrandMark } from "@/components/brand-mark";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="brand-shell min-h-screen px-6 py-8">
      <div className="relative mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-8 lg:grid-cols-[1.15fr_1fr]">
        <section className="rounded-3xl border border-brand-200 bg-white/75 p-8 shadow-panel backdrop-blur-sm">
          <BrandMark />
          <p className="mt-6 max-w-xl text-sm text-ink/85">
            Plataforma interna para documentacion clinica asistida. Los borradores requieren revision y validacion
            profesional antes de su uso.
          </p>
        </section>

        <section className="relative flex justify-center lg:justify-end">{children}</section>
      </div>
    </div>
  );
}

