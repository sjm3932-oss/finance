"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

type Listener = () => void;

let busy = false;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l();
}

export function markNavStart() {
  if (busy) return;
  busy = true;
  emit();
}

export function markNavEnd() {
  if (!busy) return;
  busy = false;
  emit();
}

function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return busy;
}

function getServerSnapshot() {
  return false;
}

/** Call on route change / soft-nav settle so the busy bar clears. */
export function useClearNavBusy() {
  const pathname = usePathname();
  useEffect(() => {
    markNavEnd();
  }, [pathname]);
}

export function useNavBusy() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function NavBusyBar() {
  useClearNavBusy();
  const pending = useNavBusy();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (pending) {
      setVisible(true);
      return;
    }
    const t = window.setTimeout(() => setVisible(false), 180);
    return () => window.clearTimeout(t);
  }, [pending]);

  if (!visible) return null;

  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden"
      aria-hidden
    >
      <div
        className={`h-full w-1/3 rounded-full bg-brand ${
          pending ? "animate-[nav-busy_0.9s_ease-in-out_infinite]" : "opacity-0"
        }`}
      />
    </div>
  );
}
