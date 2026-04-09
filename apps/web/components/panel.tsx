import { ReactNode } from "react";

interface PanelProps {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Panel({ title, children, actions }: PanelProps) {
  return (
    <section className="rounded-2xl border border-brand-200 bg-white/95 p-4 shadow-panel sm:p-5">
      <header className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {actions ? <div className="flex flex-wrap gap-1">{actions}</div> : null}
      </header>
      <div className="text-sm text-slate-700">{children}</div>
    </section>
  );
}
