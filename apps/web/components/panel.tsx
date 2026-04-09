import { ReactNode } from "react";

interface PanelProps {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Panel({ title, children, actions }: PanelProps) {
  return (
    <section className="rounded-2xl border border-brand-200 bg-white/95 p-5 shadow-panel">
      <header className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {actions}
      </header>
      <div className="text-sm text-slate-700">{children}</div>
    </section>
  );
}
