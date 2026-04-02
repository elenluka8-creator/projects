"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AppShell } from "@/components/AppShell";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { api, ApiError, type Job, type DownloadUrlResponse } from "@/lib/api";

const POLL_INTERVAL_MS = 4000;
const ACTIVE_STATUSES = new Set(["validating", "queued", "processing"]);

function translateStage(
  t: ReturnType<typeof useTranslations<"jobDetail">>,
  stage: string,
): string {
  const stages = t.raw("stages") as Record<string, string> | undefined;
  return stages?.[stage] ?? stage;
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-start justify-between gap-4 py-3 border-b last:border-0"
      style={{ borderColor: "#ede8e0" }}
    >
      <span className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
        {label}
      </span>
      <span className="text-sm font-medium text-right" style={{ color: "var(--color-navy)" }}>
        {value}
      </span>
    </div>
  );
}

function RetryJobButton({ jobId }: { jobId: string }) {
  const t = useTranslations("jobDetail");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRetry = async () => {
    setState("loading");
    setErrorMsg(null);
    try {
      const newJob = await api.retryJob(jobId);
      router.push(`/${locale}/jobs/${newJob.job_id}`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : t("retryError");
      setErrorMsg(msg);
      setState("error");
    }
  };

  if (state === "error" && errorMsg) {
    return (
      <div>
        <p className="error-text mb-2">{errorMsg}</p>
        <button type="button" className="btn-secondary" onClick={() => setState("idle")}>
          {tCommon("dismiss")}
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      className="btn-primary"
      onClick={() => void handleRetry()}
      disabled={state === "loading"}
    >
      {state === "loading" ? t("retrying") : t("retryLabel")}
    </button>
  );
}

function DownloadButton({ jobId }: { jobId: string }) {
  const t = useTranslations("jobDetail");
  const tCommon = useTranslations("common");
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleDownload = async () => {
    setState("loading");
    try {
      const result: DownloadUrlResponse = await api.getDownloadUrl(jobId);
      setState("ready");
      window.location.href = result.download_url;
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : t("downloadError"));
      setState("error");
    }
  };

  if (state === "error") {
    return (
      <div>
        <p className="error-text mb-2">{errorMsg}</p>
        <button type="button" className="btn-secondary" onClick={() => setState("idle")}>
          {tCommon("retry")}
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      className="btn-primary"
      onClick={handleDownload}
      disabled={state === "loading"}
    >
      {state === "loading" ? t("downloading") : t("download")}
    </button>
  );
}

function useJobDetail(jobId: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      const j = await api.getJob(jobId);
      setJob(j);
      setError(null);
      return j;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void fetchJob();

    const schedule = () => {
      timerRef.current = setTimeout(async () => {
        const j = await fetchJob();
        if (j && ACTIVE_STATUSES.has(j.status)) {
          schedule();
        }
      }, POLL_INTERVAL_MS);
    };

    schedule();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchJob]);

  return { job, loading, error };
}

export default function JobDetailPage() {
  const t = useTranslations("jobDetail");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();
  const { job, loading, error } = useJobDetail(id);

  if (loading) {
    return (
      <AppShell>
        <p className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.5 }}>
          {tCommon("loading")}
        </p>
      </AppShell>
    );
  }

  if (error || !job) {
    return (
      <AppShell>
        <p className="error-text mb-4">{error ?? t("notFound")}</p>
        <Link href={`/${locale}/jobs`} className="btn-secondary">
          {t("backButton")}
        </Link>
      </AppShell>
    );
  }

  const langLabel =
    new Intl.DisplayNames([locale], { type: "language" }).of(job.target_language) ??
    job.target_language;

  const createdAt = new Date(job.created_at).toLocaleString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const deadline = job.retention_deadline
    ? new Date(job.retention_deadline).toLocaleDateString(locale, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  const isActive = ACTIVE_STATUSES.has(job.status);

  const etaSeconds = job.eta_seconds_remaining ?? null;
  const etaText =
    etaSeconds != null && etaSeconds > 0
      ? etaSeconds < 60
        ? t("etaSeconds", { seconds: etaSeconds })
        : t("etaMinutes", { minutes: Math.round(etaSeconds / 60) })
      : null;

  return (
    <AppShell>
      <div className="max-w-content mx-auto">
        <Link
          href={`/${locale}/jobs`}
          className="mb-6 inline-block text-sm"
          style={{ color: "var(--color-navy)", opacity: 0.55 }}
        >
          {t("backToBooks")}
        </Link>

        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-2xl" style={{ color: "var(--color-navy)" }}>
              {job.book_title ?? t("untitled")}
            </h1>
            {job.book_author && (
              <p className="mt-1 text-sm" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
                {job.book_author}
              </p>
            )}
          </div>
          <JobStatusBadge variant="detail" status={job.status} />
        </div>

        {isActive && (
          <div
            className="mb-6 rounded-lg px-4 py-4"
            style={{ backgroundColor: "rgba(232,168,73,0.1)", border: "1px solid #e8a849" }}
          >
            <div className="flex items-start gap-3">
              <svg
                className="shrink-0 animate-spin mt-0.5"
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                aria-hidden="true"
              >
                <circle cx="8" cy="8" r="6" stroke="#ede8e0" strokeWidth="2.5" />
                <path
                  d="M8 2a6 6 0 0 1 6 6"
                  stroke="var(--color-navy)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              </svg>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium" style={{ color: "var(--color-navy)" }}>
                  {job.status === "queued"
                    ? t("queuedStatus")
                    : job.pipeline_stage
                    ? t("processingStage", {
                        stage: translateStage(t, job.pipeline_stage),
                      })
                    : t("processingBook")}
                </p>
                {(job.progress_percent ?? 0) > 0 && (
                  <>
                    <div
                      className="mt-3 h-2 w-full max-w-md overflow-hidden rounded-full"
                      style={{ backgroundColor: "#ede8e0" }}
                    >
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, job.progress_percent ?? 0)}%`,
                          backgroundColor: "var(--color-amber)",
                        }}
                      />
                    </div>
                    <p className="mt-2 text-xs" style={{ color: "var(--color-navy)", opacity: 0.65 }}>
                      {t("percentComplete", { percent: job.progress_percent ?? 0 })}
                      {etaText ? ` · ${etaText}` : ""}
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {job.status === "failed" && job.failure_reason && (
          <div
            className="mb-6 rounded-lg px-4 py-3"
            style={{ backgroundColor: "rgba(192,57,43,0.07)", border: "1px solid #c0392b" }}
          >
            <p className="text-sm" style={{ color: "var(--color-error)" }}>
              {job.failure_reason}
            </p>
          </div>
        )}

        <div className="card mb-6">
          <MetaRow
            label={t("modeLabel")}
            value={job.mode === "guided" ? t("modeGuided") : t("modeTranslate")}
          />
          <MetaRow label={t("targetLangLabel")} value={langLabel} />
          {job.translation_style && (
            <MetaRow
              label={t("styleLabel")}
              value={job.translation_style === "literal" ? t("styleLiteral") : t("styleNatural")}
            />
          )}
          {job.mode === "guided" && job.user_level && (
            <MetaRow label={t("levelLabel")} value={job.user_level} />
          )}
          {job.mode === "guided" && job.explanation_depth && (
            <MetaRow
              label={t("depthLabel")}
              value={
                job.explanation_depth === "minimal"
                  ? t("depthMinimal")
                  : job.explanation_depth === "detailed"
                  ? t("depthDetailed")
                  : t("depthStandard")
              }
            />
          )}
          {job.word_count_estimate != null && (
            <MetaRow
              label={t("wordsLabel")}
              value={job.word_count_estimate.toLocaleString(locale)}
            />
          )}
          <MetaRow label={t("submittedLabel")} value={createdAt} />
          {deadline && <MetaRow label={t("availableUntilLabel")} value={deadline} />}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {job.status === "completed" && <DownloadButton jobId={job.job_id} />}

          {job.status === "failed" && job.retry_eligible && (
            <RetryJobButton jobId={job.job_id} />
          )}

          <Link
            href={`/${locale}/upload`}
            className="text-sm"
            style={{ color: "var(--color-navy)", opacity: 0.6 }}
          >
            {t("uploadNew")}
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
