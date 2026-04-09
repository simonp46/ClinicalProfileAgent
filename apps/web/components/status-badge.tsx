interface StatusBadgeProps {
  value: string;
}

const styles: Record<string, string> = {
  scheduled: "bg-slate-100 text-slate-700",
  processing: "bg-amber-100 text-amber-800",
  ready_for_review: "bg-brand-100 text-brand-800",
  approved: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

export function StatusBadge({ value }: StatusBadgeProps) {
  return (
    <span
      className={`rounded-full border border-white/60 px-2 py-1 text-xs font-semibold ${
        styles[value] ?? "bg-slate-100 text-slate-700"
      }`}
    >
      {value}
    </span>
  );
}
