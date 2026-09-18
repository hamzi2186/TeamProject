import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

interface MetricCardProps {
  label: string;
  value: number | string;
  subtext?: string;
  accentColor?: string;
  size?: "compact" | "large";
}

function useCountUp(target: number, duration = 450): number {
  const reduceMotion = useReducedMotion();
  const [display, setDisplay] = useState(reduceMotion ? target : 0);
  const frame = useRef<ReturnType<typeof requestAnimationFrame> | null>(null);

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(target);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(target * eased));
      if (progress < 1) {
        frame.current = requestAnimationFrame(tick);
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [target, duration, reduceMotion]);

  return display;
}

export function MetricCard({ label, value, subtext, accentColor, size = "compact" }: MetricCardProps) {
  const numeric = typeof value === "number";
  const animated = numeric ? useCountUp(value) : undefined;

  return (
    <div
      className="rounded-lg border border-border bg-card p-4 shadow-sm"
      style={accentColor ? { borderTop: `3px solid ${accentColor}` } : undefined}
    >
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className={`mt-1 font-semibold tracking-tight text-foreground ${
          size === "large" ? "text-[30px]" : "text-[22px]"
        }`}
      >
        {numeric ? animated : value}
      </p>
      {subtext && <p className="mt-1 text-[11px] text-muted-foreground">{subtext}</p>}
    </div>
  );
}