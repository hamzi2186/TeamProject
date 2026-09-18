import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n);
}

export function formatDateTime(iso: string | undefined | null): string {
  if (!iso) return "N/A";
  return new Date(iso).toLocaleString();
}