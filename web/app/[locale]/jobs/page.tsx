"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AppShell } from "@/components/AppShell";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { api, type Job } from "@/lib/api";

const POLL_INTERVAL_MS = 5000;
const ACTIVE_STATUSES = new Set(["validating", "queued", "processing"]);

function JobRow({ job }: { job: Job }) {
  const t = useTranslations("jobs");
  const locale = useLocale();

  const date = new Date(job.created_at).toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const modeName = job.mode === "guided" ? t("modeGuided") : t("modeTranslate");
  const langLabel =
    new Intl.DisplayNames([locale], { type: "language" }).of(job.target_language) ??
    job.target_language;

  const etaSeconds = job.eta_seconds_remaining ?? null;
  const etaText =
    etaSeconds != null && etaSeconds > 0
      ? etaSeconds < 60
        ? t("etaSeconds", { seconds: etaSeconds })
        : t("etaMinutes", { minutes: Math.round(etaSeconds / 60) })
      : null;

  return (
    <Link
      href={`/${locale}/jobs/${job.job_id}`}
      className="flex items-center justify-between gap-4 rounded-lg border px-4 py-4 transition-colors"
      style={{ borderColor: "#ede8e0", backgroundColor: "#fff" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--color-navy)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "#ede8e0";
      }}
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium" style={{ color: "var(--color-navy)" }}>
          {job.book_title ?? t("untitled")}
        </p>
        <p className="mt-0.5 text-xs" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
          {modeName} → {langLabel} · {date}
        </p>
        {ACTIVE_STATUSES.has(job.status) && job.progress_percent != null && job.progress_percent > 0 && (
          <div className="mt-2 max-w-xs">
            <div
              className="h-1 w-full overflow-hidden rounded-full"
              style={{ backgroundColor: "#ede8e0" }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(100, job.progress_percent)}%`,
                  backgroundColor: "var(--color-amber)",
                }}
              />
            </div>
            <p className="mt-1 text-xs" style={{ color: "var(--color-navy)", opacity: 0.45 }}>
              {job.pipeline_stage
                ? `${(t.raw("stages") as Record<string, string>)?.[job.pipeline_stage] ?? job.pipeline_stage} · `
                : ""}
              {job.progress_percent}%
              {etaText ? ` · ${etaText}` : ""}
            </p>
          </div>
        )}
      </div>
      <JobStatusBadge status={job.status} />
    </Link>
  );
}

function useJobsList() {
  const t = useTranslations("jobs");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchJobs = async () => {
    try {
      const list = await api.listJobs();
      setJobs(list);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("failedToLoad"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchJobs();

    const schedule = () => {
      timerRef.current = setTimeout(async () => {
        await fetchJobs();
        const current = await api.listJobs().catch(() => []);
        if (current.some((j) => ACTIVE_STATUSES.has(j.status))) {
          schedule();
        }
      }, POLL_INTERVAL_MS);
    };

    schedule();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { jobs, loading, error };
}

export default function JobsPage() {
  const t = useTranslations("jobs");
  const locale = useLocale();
  const tCommon = useTranslations("common");
  const { jobs, loading, error } = useJobsList();

  return (
    <AppShell>
      <div className="max-w-content mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="font-heading text-2xl" style={{ color: "var(--color-navy)" }}>
            {t("title")}
          </h1>
          <Link href={`/${locale}/upload`} className="btn-primary text-sm">
            {t("newBook")}
          </Link>
        </div>

        {loading && (
          <p className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.5 }}>
            {tCommon("loading")}
          </p>
        )}

        {!loading && error && <p className="error-text">{error}</p>}

        {!loading && !error && jobs.length === 0 && (
          <div className="card py-12 text-center">
            <p className="font-heading text-lg mb-2" style={{ color: "var(--color-navy)" }}>
              {t("emptyTitle")}
            </p>
            <p className="text-sm mb-6" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
              {t("emptyDesc")}
            </p>
            <Link href={`/${locale}/upload`} className="btn-primary">
              {t("uploadBook")}
            </Link>
          </div>
        )}

        {!loading && !error && jobs.length > 0 && (
          <ul className="space-y-3" role="list">
            {jobs.map((job) => (
              <li key={job.job_id}>
                <JobRow job={job} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
