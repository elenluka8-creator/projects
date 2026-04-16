"use client";

import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AppShell } from "@/components/AppShell";
import { api, type PrecheckResult, type CreditEstimate, type CreditsBalance } from "@/lib/api";

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
// Normalize text: collapse whitespace, trim
// ---------------------------------------------------------------------------

function normalizeText(text: string): string {
  return text
    .replace(/\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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

function SourceLanguageCard({
  detectedLanguage,
  locale,
  t,
}: {
  detectedLanguage: string | null;
  locale: string;
  t: ReturnType<typeof useTranslations<"upload">>;
}) {
  const langName = detectedLanguage
    ? new Intl.DisplayNames([locale], { type: "language" }).of(detectedLanguage) ?? detectedLanguage
    : t("precheck_langUnknown");

  return (
    <div
      className="rounded-lg border px-4 py-3 flex items-center gap-3"
      style={{ borderColor: "#d4cfc8", backgroundColor: "#faf6ef" }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="7" stroke="#e8a849" strokeWidth="1.5" />
        <path d="M8 5v3.5l2 1.5" stroke="#e8a849" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <p className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.7 }}>
        {t("sourceLangDetected")} <strong style={{ opacity: 1 }}>{langName}</strong>
      </p>
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
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string; description?: string }[];
  error?: string | null;
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
        style={{ maxWidth: "320px", borderColor: error ? "var(--color-error)" : undefined }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {error && <p className="error-text mt-1">{error}</p>}
      {!error && selected?.description && (
        <p className="mt-1 text-xs" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
          {selected.description}
        </p>
      )}
    </div>
  );
}

function WhatYouGetBlock({ mode, t }: {
  mode: "translate" | "guided";
  t: ReturnType<typeof useTranslations<"upload">>;
}) {
  const items = mode === "guided"
    ? [t("wyg_translated"), t("wyg_format"), t("wyg_explanations")]
    : [t("wyg_translated"), t("wyg_format"), t("wyg_cancel")];

  return (
    <div
      className="rounded-lg px-4 py-4"
      style={{ backgroundColor: "rgba(232,168,73,0.07)", border: "1px solid rgba(232,168,73,0.4)" }}
    >
      <p className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: "var(--color-navy)", opacity: 0.5 }}>
        {t("wyg_title")}
      </p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-2 text-sm" style={{ color: "var(--color-navy)" }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <circle cx="7" cy="7" r="6.5" fill="rgba(232,168,73,0.2)" stroke="#e8a849" />
              <path d="M4.5 7l2 2 3-3" stroke="#1a1f36" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {item}
          </li>
        ))}
      </ul>
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
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const { phase, run, reset } = useUploadFlow(t);

  const [mode, setMode] = useState<"translate" | "guided">("translate");
  const [qualityTier, setQualityTier] = useState<"express" | "standard" | "premium">("express");
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [translationStyle, setTranslationStyle] = useState("natural");
  const [userLevel, setUserLevel] = useState("B1");
  const [explanationDepth, setExplanationDepth] = useState("standard");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [balance, setBalance] = useState<CreditsBalance | null>(null);
  const [estimate, setEstimate] = useState<CreditEstimate | null>(null);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const detectedLanguage = phase.name === "done" ? (phase.precheck.detected_language ?? "") : "";
  const wordCount = phase.name === "done" ? (phase.precheck.word_count ?? 0) : 0;

  // Default target language to first language that is NOT the detected source language
  useEffect(() => {
    if (phase.name === "done" && detectedLanguage) {
      const first = TARGET_LANGUAGE_CODES.find((c) => c !== detectedLanguage);
      if (first) setTargetLanguage(first);
    }
  }, [phase.name, detectedLanguage]);

  const sameLangError =
    phase.name === "done" && detectedLanguage && detectedLanguage === targetLanguage
      ? t("error_sameLang")
      : null;

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
    {
      value: "express" as const,
      label: t("tierExpressLabel"),
      description: t("tierExpressDesc"),
      badge: t("tierRecommended"),
    },
    { value: "standard" as const, label: t("tierStandardLabel"), description: t("tierStandardDesc") },
    { value: "premium" as const, label: t("tierPremiumLabel"), description: t("tierPremiumDesc") },
  ], [t]);

  useEffect(() => {
    api.getCredits().then(setBalance).catch(() => { /* non-critical */ });
  }, []);

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
    !sameLangError &&
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
          <form onSubmit={handleSubmit} className="space-y-6">

            {/* Source language detected */}
            <SourceLanguageCard
              detectedLanguage={phase.precheck.detected_language}
              locale={locale}
              t={t}
            />

            {/* Target language — primary, always visible */}
            <SelectField
              id="target-language"
              label={t("targetLangLabel")}
              value={targetLanguage}
              onChange={setTargetLanguage}
              options={TARGET_LANGUAGES}
              error={sameLangError}
            />

            <div style={{ borderTop: "1px solid #ede8e0" }} />

            {/* What you get */}
            <WhatYouGetBlock mode={mode} t={t} />

            {/* Advanced settings toggle */}
            <div>
              <button
                type="button"
                className="flex items-center gap-2 text-sm"
                style={{ color: "var(--color-navy)", opacity: 0.6 }}
                onClick={() => setAdvancedOpen((o) => !o)}
                aria-expanded={advancedOpen}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  className="transition-transform"
                  style={{ transform: advancedOpen ? "rotate(90deg)" : "rotate(0deg)" }}
                  aria-hidden="true"
                >
                  <path d="M4 2l6 5-6 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {advancedOpen ? t("advancedHide") : t("advancedShow")}
              </button>
            </div>

            {advancedOpen && (
              <div className="space-y-6 rounded-lg border p-4" style={{ borderColor: "#ede8e0" }}>
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
                        badge={tier.badge}
                      />
                    ))}
                  </div>
                </fieldset>

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
              </div>
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
