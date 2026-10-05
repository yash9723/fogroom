import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value.toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

export function seconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "-";
  return `${(ms / 1000).toFixed(1)}s`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

/** Score -> semantic tone used by meters and badges. */
export function scoreTone(score: number | null | undefined): "ok" | "warn" | "crit" | "off" {
  if (score === null || score === undefined) return "off";
  if (score >= 70) return "ok";
  if (score >= 45) return "warn";
  return "crit";
}

/** Uncertainty is inverted: high is bad. */
export function uncertaintyTone(value: number | null | undefined): "ok" | "warn" | "crit" | "off" {
  if (value === null || value === undefined) return "off";
  if (value < 35) return "ok";
  if (value < 55) return "warn";
  return "crit";
}
