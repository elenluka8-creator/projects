"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AppShell } from "@/components/AppShell";
import { api, type PrecheckResult, type CreditEstimate, type CreditsBalance } from "@/lib/api";

function useHasJobs(): boolean {
  const [hasJobs, setHasJobs] = useState(false);
  useEffect(() => {
    api.listJobs().then((jobs) => setHasJobs(jobs.length > 0)).catch(() => {});
  }, []);
  return hasJobs;
}

const MAX_FILE_BYTES = 50 * 1024 * 1024;

const TARGET_LANGUAGE_CODES = ["en", "es", "fr", "de", "it", "pt", "nl", "ru", "pl", "sr", "ja", "zh", "ko", "tr"];

// ---------------------------------------------------------------------------
// Upload phase machine
// ---------------------------------------------------------------------------

type Phase =
  | { name: "idle" }
  | { name: "uploading"; progress: number; filename: string }
  | { name: "confirming"; filename: string }
  | { name: "prechecking"; filename: string }
  | { name: "done"; filename: string; artifactId: string; precheck: PrecheckResult }
  | { name: "error"; message: string };

function useUploadFlow(t: ReturnType<typeof useTranslations<"upload">>) {
  const [phase, setPhase] = useState<Phase>({ name: "idle" });

  const run = useCallback(async (file: File) => {
    setPhase({ name: "uploading", progress: 0, filename: file.name });

    const jobId = crypto.randomUUID();
    let reg;
    try {
      reg = await api.registerArtifact(jobId, "source_epub");
    } catch (err) {
      setPhase({ name: "error", message: errorMessage(err, t) });
      return;
    }

    try {
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setPhase({
              name: "uploading",
              progress: Math.round((e.loaded / e.total) * 100),
              filename: file.name,
            });
          }
        };
        xhr.onload = () => {
          xhr.status === 200 || xhr.status === 204
            ? resolve()
            : reject(new Error(`S3 upload returned HTTP ${xhr.status}`));
        };
        xhr.onerror = () => reject(new Error("Network error during S3 upload"));
        xhr.open("PUT", reg.upload_url);
        xhr.setRequestHeader("Content-Type", "application/epub+zip");
        xhr.send(file);
      });
    } catch (err) {
      setPhase({ name: "error", message: errorMessage(err, t) });
      return;
    }

    setPhase({ name: "confirming", filename: file.name });
    try {
      await api.confirmUpload(reg.artifact_id);
    } catch (err) {
      setPhase({ name: "error", message: errorMessage(err, t) });
      return;
    }

    setPhase({ name: "prechecking", filename: file.name });
    let precheck: PrecheckResult;
    try {
      precheck = await api.runPrecheck(reg.artifact_id);
    } catch (err) {
      setPhase({ name: "error", message: errorMessage(err, t) });
      return;
    }

    if (precheck.status === "failed") {
      setPhase({
        name: "error",
        message: precheck.error_code
          ? t("error_validationFailed", { code: precheck.error_code })
          : t("error_validationFailedGeneric"),
      });
      return;
    }

    setPhase({ name: "done", filename: file.name, artifactId: reg.artifact_id, precheck });
  }, [t]);

  const reset = useCallback(() => setPhase({ name: "idle" }), []);

  return { phase, run, reset };
}

function errorMessage(err: unknown, t: ReturnType<typeof useTranslations<"upload">>): string {
  return err instanceof Error ? err.message : t("error_unexpected");
}

function validateFile(file: File, t: ReturnType<typeof useTranslations<"upload">>): string | null {
  if (!file.name.toLowerCase().endsWith(".epub")) return t("error_invalidType");
  if (file.size > MAX_FILE_BYTES) return t("error_tooLarge");
  return null;
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "#ede8e0" }}>
      <div
        className="h-full rounded-full transition-all duration-200"
        style={{ width: `${value}%`, backgroundColor: "var(--color-amber)" }}
      />
    </div>
  );
}

function DropZone({
  onFile,
  disabled,
  t,
}: {
  onFile: (f: File) => void;
  disabled: boolean;
  t: ReturnType<typeof useTranslations<"upload">>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const handle = (file: File) => {
    setFileError(null);
    const err = validateFile(file, t);
    if (err) { setFileError(err); return; }
    onFile(file);
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label={t("dropzone_ariaLabel")}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => !disabled && e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (disabled) return;
          const file = e.dataTransfer.files?.[0];
          if (file) handle(file);
        }}
        className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-8 py-16 text-center transition-colors"
        style={{
          borderColor: dragging ? "var(--color-navy)" : "#d4cfc8",
          backgroundColor: dragging ? "rgba(26,31,54,0.03)" : "#fff",
          cursor: disabled ? "default" : "pointer",
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <svg className="mb-4" width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <rect width="40" height="40" rx="8" fill="#faf6ef" />
          <path d="M20 26V14M20 14l-4 4M20 14l4 4" stroke="#1a1f36" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M12 28h16" stroke="#e8a849" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <p className="text-sm font-medium" style={{ color: "var(--color-navy)" }}>
          {t("dropzone_prompt")}{" "}
          <span style={{ color: "var(--color-amber-dark)", textDecoration: "underline" }}>
            {t("dropzone_browse")}
          </span>
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--color-navy)", opacity: 0.5 }}>
          {t("dropzone_hint")}
        </p>
      </div>
      {fileError && <p className="error-text mt-2">{fileError}</p>}
      <input
        ref={inputRef}
        type="file"
        accept=".epub,application/epub+zip"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handle(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function PrecheckCard({
  precheck,
  filename,
  t,
  locale,
}: {
  precheck: PrecheckResult;
  filename: string;
  t: ReturnType<typeof useTranslations<"upload">>;
  locale: string;
}) {
  const lang = precheck.detected_language
    ? new Intl.DisplayNames([locale], { type: "language" }).of(precheck.detected_language) ??
      precheck.detected_language
    : t("precheck_langUnknown");

  return (
    <div className="card space-y-4">
      <div>
        <p className="label">{t("precheck_file")}</p>
        <p className="text-sm font-medium truncate" style={{ color: "var(--color-navy)" }}>
          {filename}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="label">{t("precheck_language")}</p>
          <p className="text-sm" style={{ color: "var(--color-navy)" }}>{lang}</p>
        </div>
        <div>
          <p className="label">{t("precheck_words")}</p>
          <p className="text-sm" style={{ color: "var(--color-navy)" }}>
            {precheck.word_count != null ? precheck.word_count.toLocaleString(locale) : "—"}
          </p>
        </div>
        <div>
          <p className="label">{t("precheck_chapters")}</p>
          <p className="text-sm" style={{ color: "var(--color-navy)" }}>
            {precheck.chapter_count ?? "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

function ModeCard({
  label,
  description,
  selected,
  onSelect,
  badge,
}: {
  label: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  badge?: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className="w-full rounded-lg border-2 p-4 text-left transition-colors"
      style={{
        borderColor: selected ? "var(--color-navy)" : "#d4cfc8",
        backgroundColor: selected ? "rgba(26,31,54,0.03)" : "#fff",
      }}
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2"
          style={{
            borderColor: selected ? "var(--color-navy)" : "#d4cfc8",
            backgroundColor: selected ? "var(--color-navy)" : "transparent",
          }}
          aria-hidden="true"
        >
          {selected && <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#fff" }} />}
        </span>
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium" style={{ color: "var(--color-navy)" }}>{label}</p>
            {badge && (
              <span
                className="rounded-full px-2 py-0.5 text-xs font-semibold"
                style={{ backgroundColor: "var(--color-amber)", color: "var(--color-navy)" }}
              >
                {badge}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
            {description}
          </p>
        </div>
      </div>
    </button>
  );
}

function SelectField({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string; description?: string }[];
}) {
  const selected = options.find((o) => o.value === value);
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <select
        id={id}
        className="input-field mt-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ maxWidth: "320px" }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {selected?.description && (
        <p className="mt-1 text-xs" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
          {selected.description}
        </p>
      )}
    </div>
  );
}

function BalanceDisplay({
  balance,
  estimate,
  estimateLoading,
  t,
}: {
  balance: number | null;
  estimate: CreditEstimate | null;
  estimateLoading: boolean;
  t: ReturnType<typeof useTranslations<"upload">>;
}) {
  if (balance === null) return null;

  const remaining = estimate !== null ? balance - estimate.estimated_credits : null;
  const insufficient = remaining !== null && remaining < 0;

  const tierLabel = (tier: string) => {
    if (tier === "standard") return t("tierStandard");
    if (tier === "experimental") return t("tierExperimental");
    return tier;
  };

  const navy = "#1a1f36";
  const row: React.CSSProperties = {
    fontSize: "0.95rem",
    fontWeight: 500,
    color: navy,
    margin: 0,
  };

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: insufficient ? "#e53e3e" : "#e8a849",
        backgroundColor: insufficient ? "rgba(192,57,43,0.04)" : "rgba(232,168,73,0.06)",
        display: "flex",
        flexDirection: "column",
        gap: "0.3rem",
      }}
    >
      <p style={row}>{t("balance_label")} {balance} {t("balance_credits")}</p>

      {estimateLoading ? (
        <p style={{ ...row, opacity: 0.5 }}>{t("balance_calculating")}</p>
      ) : estimate ? (
        <>
          <p style={row}>
            {t("balance_thisTranslation")} {estimate.estimated_credits} {t("balance_credits")}
          </p>

          <p style={{ ...row, color: insufficient ? "#c0392b" : navy }}>
            {t("balance_afterTranslation")} {remaining} {t("balance_remaining")}
          </p>

          {insufficient && (
            <p style={{ ...row, color: "#c0392b" }}>{t("balance_insufficient")}</p>
          )}

          {estimate.validation_errors.length > 0 && (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {estimate.validation_errors.map((e) => (
                <li key={e} style={{ ...row, color: "#c0392b" }}>{e}</li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function UploadPage() {
  const t = useTranslations("upload");
  const tNav = useTranslations("nav");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const { phase, run, reset } = useUploadFlow(t);
  const hasJobs = useHasJobs();

  const [mode, setMode] = useState<"translate" | "guided">("translate");
  const [qualityTier, setQualityTier] = useState<"express" | "standard" | "premium">("express");
  const [targetLanguage, setTargetLanguage] = useState("ru");
  const [translationStyle, setTranslationStyle] = useState("natural");
  const [userLevel, setUserLevel] = useState("B1");
  const [explanationDepth, setExplanationDepth] = useState("standard");

  const [balance, setBalance] = useState<CreditsBalance | null>(null);
  const [estimate, setEstimate] = useState<CreditEstimate | null>(null);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const MODES = useMemo(() => [
    { value: "translate" as const, label: t("modeTranslateLabel"), description: t("modeTranslateDesc") },
    { value: "guided" as const, label: t("modeGuidedLabel"), description: t("modeGuidedDesc") },
  ], [t]);

  const TARGET_LANGUAGES = useMemo(() => {
    const dn = new Intl.DisplayNames([locale], { type: "language" });
    return TARGET_LANGUAGE_CODES.map((code) => ({
      value: code,
      label: dn.of(code) ?? code,
    }));
  }, [locale]);

  const TRANSLATION_STYLES = useMemo(() => [
    { value: "literal", label: t("styleLiteralLabel"), description: t("styleLiteralDesc") },
    { value: "natural", label: t("styleNaturalLabel"), description: t("styleNaturalDesc") },
  ], [t]);

  const USER_LEVELS = useMemo(() => [
    { value: "A1", label: t("levelA1Label"), description: t("levelA1Desc") },
    { value: "A2", label: t("levelA2Label"), description: t("levelA2Desc") },
    { value: "B1", label: t("levelB1Label"), description: t("levelB1Desc") },
    { value: "B2", label: t("levelB2Label"), description: t("levelB2Desc") },
    { value: "C1", label: t("levelC1Label"), description: t("levelC1Desc") },
  ], [t]);

  const EXPLANATION_DEPTHS = useMemo(() => [
    { value: "minimal", label: t("depthMinimalLabel"), description: t("depthMinimalDesc") },
    { value: "standard", label: t("depthStandardLabel"), description: t("depthStandardDesc") },
    { value: "detailed", label: t("depthDetailedLabel"), description: t("depthDetailedDesc") },
  ], [t]);

  const QUALITY_TIERS = useMemo(() => [
    { value: "express"  as const, label: t("tierExpressLabel"),  description: t("tierExpressDesc")  },
    { value: "standard" as const, label: t("tierStandardLabel"), description: t("tierStandardDesc") },
    { value: "premium"  as const, label: t("tierPremiumLabel"),  description: t("tierPremiumDesc")  },
  ], [t]);

  useEffect(() => {
    api.getCredits().then(setBalance).catch(() => { /* non-critical */ });
  }, []);

  const wordCount = phase.name === "done" ? (phase.precheck.word_count ?? 0) : 0;
  const detectedLanguage = phase.name === "done" ? (phase.precheck.detected_language ?? "") : "";

  const fetchEstimate = useCallback(
    async (m: string, lang: string, style: string, level: string, depth: string, tier: string, wc: number, srcLang: string) => {
      if (!wc) return;
      setEstimateLoading(true);
      setEstimateError(null);
      try {
        const result = await api.estimateCredits({
          mode: m, targetLanguage: lang, wordCount: wc,
          sourceLanguage: srcLang || undefined,
          translationStyle: style, userLevel: level, explanationDepth: depth,
          qualityTier: tier,
        });
        setEstimate(result);
      } catch (err) {
        setEstimateError(err instanceof Error ? err.message : tCommon("loading"));
      } finally {
        setEstimateLoading(false);
      }
    },
    [tCommon],
  );

  useEffect(() => {
    if (phase.name !== "done") return;
    void fetchEstimate(mode, targetLanguage, translationStyle, userLevel, explanationDepth, qualityTier, wordCount, detectedLanguage);
  }, [phase.name, mode, targetLanguage, translationStyle, userLevel, explanationDepth, qualityTier, wordCount, detectedLanguage, fetchEstimate]);

  const balanceValue = balance?.balance ?? null;
  const remaining = balanceValue !== null && estimate ? balanceValue - estimate.estimated_credits : null;
  const insufficient = remaining !== null && remaining < 0;

  const canSubmit =
    phase.name === "done" &&
    !submitting &&
    !estimateLoading &&
    !insufficient &&
    (estimate?.is_valid ?? true);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || phase.name !== "done") return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.submitJob({
        mode,
        target_language: targetLanguage,
        source_language_override: detectedLanguage || undefined,
        translation_style: translationStyle,
        user_level: userLevel,
        explanation_depth: explanationDepth,
        quality_tier: qualityTier,
        source_artifact_id: phase.artifactId,
        word_count_estimate: wordCount || undefined,
        credit_estimate: estimate?.estimated_credits ?? 0,
        ui_locale: locale,
      });
      router.push(`/${locale}/jobs`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : tCommon("loading"));
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-content mx-auto">
        {hasJobs && (
          <Link
            href={`/${locale}/jobs`}
            className="mb-6 inline-block text-sm"
            style={{ color: "var(--color-navy)", opacity: 0.55 }}
          >
            {`← ${tNav("jobs")}`}
          </Link>
        )}
        <h1 className="font-heading mb-2 text-2xl" style={{ color: "var(--color-navy)" }}>
          {t("title")}
        </h1>
        <p className="mb-8 text-sm" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
          {t("subtitle")}
        </p>

        {(phase.name === "idle" || phase.name === "error") && (
          <div className="space-y-4">
            <DropZone onFile={run} disabled={false} t={t} />
            {phase.name === "error" && (
              <div
                className="rounded border px-4 py-3"
                style={{ borderColor: "var(--color-error)", backgroundColor: "rgba(192,57,43,0.05)" }}
              >
                <p className="text-sm" style={{ color: "var(--color-error)" }}>{phase.message}</p>
                <button
                  type="button"
                  className="mt-2 text-sm underline"
                  style={{ color: "var(--color-error)" }}
                  onClick={reset}
                >
                  {t("tryAgain")}
                </button>
              </div>
            )}
          </div>
        )}

        {phase.name === "uploading" && (
          <div className="card space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium truncate max-w-xs" style={{ color: "var(--color-navy)" }}>
                {phase.filename}
              </p>
              <span className="text-sm tabular-nums" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
                {phase.progress}%
              </span>
            </div>
            <ProgressBar value={phase.progress} />
            <p className="text-xs" style={{ color: "var(--color-navy)", opacity: 0.5 }}>{t("phase_uploading")}</p>
          </div>
        )}

        {(phase.name === "confirming" || phase.name === "prechecking") && (
          <div className="card flex items-center gap-3">
            <svg className="shrink-0 animate-spin" width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <circle cx="10" cy="10" r="8" stroke="#ede8e0" strokeWidth="3" />
              <path d="M10 2a8 8 0 0 1 8 8" stroke="var(--color-navy)" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <p className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.7 }}>
              {phase.name === "confirming" ? t("phase_verifying") : t("phase_analysing")}
            </p>
          </div>
        )}

        {phase.name === "done" && (
          <form onSubmit={handleSubmit} className="space-y-8">
            <PrecheckCard precheck={phase.precheck} filename={phase.filename} t={t} locale={locale} />

            <div style={{ borderTop: "1px solid #ede8e0" }} />

            <h2 className="font-heading text-lg" style={{ color: "var(--color-navy)" }}>
              {t("configTitle")}
            </h2>

            <fieldset>
              <legend className="label mb-3" style={{ color: "var(--color-navy)" }}>
                {t("modeFieldset")}
              </legend>
              <div className="space-y-3" role="radiogroup">
                {MODES.map((m) => (
                  <ModeCard
                    key={m.value}
                    label={m.label}
                    description={m.description}
                    selected={mode === m.value}
                    onSelect={() => setMode(m.value)}
                  />
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="label mb-3" style={{ color: "var(--color-navy)" }}>
                {t("tierSectionLabel")}
              </legend>
              <div className="space-y-3" role="radiogroup">
                {QUALITY_TIERS.map((tier) => (
                  <ModeCard
                    key={tier.value}
                    label={tier.label}
                    description={tier.description}
                    selected={qualityTier === tier.value}
                    onSelect={() => setQualityTier(tier.value)}
                    badge={tier.value === "express" ? "Recommended" : undefined}
                  />
                ))}
              </div>
            </fieldset>

            <SelectField
              id="target-language"
              label={t("targetLangLabel")}
              value={targetLanguage}
              onChange={setTargetLanguage}
              options={TARGET_LANGUAGES}
            />

            <SelectField
              id="translation-style"
              label={t("styleLabel")}
              value={translationStyle}
              onChange={setTranslationStyle}
              options={TRANSLATION_STYLES}
            />

            {mode === "guided" && (
              <>
                <SelectField
                  id="user-level"
                  label={t("levelLabel")}
                  value={userLevel}
                  onChange={setUserLevel}
                  options={USER_LEVELS}
                />
                <SelectField
                  id="explanation-depth"
                  label={t("depthLabel")}
                  value={explanationDepth}
                  onChange={setExplanationDepth}
                  options={EXPLANATION_DEPTHS}
                />
              </>
            )}

            {estimateError ? (
              <p className="error-text">{estimateError}</p>
            ) : (
              <BalanceDisplay
                balance={balanceValue}
                estimate={estimate}
                estimateLoading={estimateLoading}
                t={t}
              />
            )}

            <div className="space-y-3">
              {submitError && <p className="error-text">{submitError}</p>}
              <div className="flex items-center gap-4">
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={!canSubmit}
                  aria-disabled={!canSubmit}
                >
                  {submitting ? t("submitting") : t("submit")}
                </button>
                <button
                  type="button"
                  className="text-sm"
                  style={{ color: "var(--color-navy)", opacity: 0.6 }}
                  onClick={reset}
                >
                  {t("uploadDifferent")}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </AppShell>
  );
}
