"use client";

import { useState, useTransition } from "react";
import type { ActionResult } from "@/lib/record";

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-bold text-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border border-line bg-canvas px-3 py-2.5 text-sm font-semibold text-ink outline-none focus:border-brand";

export function ActionForm({
  action,
  children,
  submitLabel,
}: {
  action: (formData: FormData) => Promise<ActionResult>;
  children: React.ReactNode;
  submitLabel: string;
}) {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pending, start] = useTransition();

  return (
    <form
      className="space-y-3"
      action={(fd) => {
        start(async () => {
          const res = await action(fd);
          setMsg({ ok: res.ok, text: res.message });
        });
      }}
    >
      {children}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-xl bg-brand px-4 py-3 text-sm font-extrabold text-white transition hover:bg-brand-dark disabled:opacity-60"
      >
        {pending ? "저장 중…" : submitLabel}
      </button>
      {msg ? (
        <p
          role="status"
          className={`rounded-xl px-3 py-2 text-sm font-semibold ${
            msg.ok
              ? "bg-brand-soft text-brand-dark"
              : "bg-rose-50 text-up"
          }`}
        >
          {msg.text}
        </p>
      ) : null}
    </form>
  );
}

export function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
      <h2 className="mb-3 text-base font-extrabold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}
