"use client";

import { useTranslations } from "next-intl";

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  validating: { bg: "rgba(232,168,73,0.12)", text: "#c4891a", dot: "#e8a849" },
  queued:     { bg: "rgba(232,168,73,0.12)", text: "#c4891a", dot: "#e8a849" },
  processing: { bg: "rgba(26,31,54,0.08)",   text: "#1a1f36", dot: "#1a1f36" },
  completed:  { bg: "rgba(52,168,83,0.12)",  text: "#2e7d32", dot: "#34a853" },
  failed:     { bg: "rgba(192,57,43,0.12)",  text: "#c0392b", dot: "#c0392b" },
  cancelled:  { bg: "rgba(0,0,0,0.06)",      text: "#666",    dot: "#999"    },
  expired:    { bg: "rgba(0,0,0,0.06)",      text: "#888",    dot: "#bbb"    },
};

export type JobStatusBadgeVariant = "list" | "detail";

type JobStatusBadgeProps = {
  status: string;
  variant?: JobStatusBadgeVariant;
};

export function JobStatusBadge({ status, variant = "list" }: JobStatusBadgeProps) {
  const t = useTranslations("status");
  const c = STATUS_COLORS[status] ?? STATUS_COLORS.expired;
  const isDetail = variant === "detail";
  const knownStatuses = ["validating", "queued", "processing", "completed", "failed", "cancelled", "expired"] as const;
  type KnownStatus = (typeof knownStatuses)[number];
  const label = knownStatuses.includes(status as KnownStatus) ? t(status as KnownStatus) : status;

  return (
    <span
      className={isDetail ? "status-badge gap-1.5 text-sm px-3 py-1" : "status-badge gap-1.5"}
      style={{ backgroundColor: c.bg, color: c.text }}
    >
      <span
        className={isDetail ? "inline-block h-2 w-2 rounded-full" : "inline-block h-1.5 w-1.5 rounded-full"}
        style={{ backgroundColor: c.dot }}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
