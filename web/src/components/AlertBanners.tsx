import type { WealthAlert } from "@/lib/portfolio";

export function AlertBanners({ alerts }: { alerts: WealthAlert[] }) {
  if (!alerts.length) return null;

  return (
    <div className="space-y-2">
      {alerts.slice(0, 5).map((a) => (
        <div
          key={a.id}
          className="rounded-2xl border border-line bg-surface px-4 py-3 shadow-soft"
        >
          <div className="text-sm font-extrabold tracking-tight">{a.title}</div>
          {a.body ? (
            <p className="mt-1 text-xs leading-relaxed text-muted">{a.body}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
