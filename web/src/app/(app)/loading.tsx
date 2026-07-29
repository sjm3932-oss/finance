export default function Loading() {
  return (
    <div className="space-y-4 animate-pulse px-0 pt-1" aria-busy="true">
      <div className="h-7 w-28 rounded-lg bg-line/80" />
      <div className="h-4 w-52 rounded bg-line/60" />
      <div className="h-11 w-full rounded-xl bg-line/50" />
      <div className="h-40 w-full rounded-2xl bg-line/45" />
      <div className="grid grid-cols-2 gap-3">
        <div className="h-24 rounded-2xl bg-line/40" />
        <div className="h-24 rounded-2xl bg-line/40" />
      </div>
      <div className="h-28 w-full rounded-2xl bg-line/40" />
    </div>
  );
}
