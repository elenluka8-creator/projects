"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type AdminJobDetail, type AdminJobRow, type AdminUserRow, type AppSettings } from "@/lib/api";

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  processing: { bg: "#dbeafe", text: "#1d4ed8" },
  queued:     { bg: "#fef9c3", text: "#854d0e" },
  completed:  { bg: "#dcfce7", text: "#166534" },
  failed:     { bg: "#fee2e2", text: "#991b1b" },
  cancelled:  { bg: "#f3f4f6", text: "#374151" },
  expired:    { bg: "#f3f4f6", text: "#374151" },
};

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {status}
    </span>
  );
}

function heartbeatAge(heartbeatAt: string | null): string {
  if (!heartbeatAt) return "—";
  const diffMs = Date.now() - new Date(heartbeatAt).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "< 1 min ago";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [jobs, setJobs] = useState<AdminJobRow[] | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<AdminJobDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [u, j, s] = await Promise.all([
        api.listAdminUsers(),
        api.listAdminJobs(),
        api.getAdminSettings(),
      ]);
      setUsers(u);
      setJobs(j);
      setSettings(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load admin data.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openJobDetail = async (jobId: string) => {
    setDetailLoading(true);
    try {
      const detail = await api.getAdminJobDetail(jobId);
      setSelectedJob(detail);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load job detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  const adjust = async (userId: string, delta: number) => {
    setBusyId(userId);
    setError(null);
    try {
      await api.adjustAdminCredits(userId, delta);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Adjustment failed.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="mb-8 flex flex-wrap gap-4">
        <Link href="/upload" className="text-sm" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
          ← Back to app
        </Link>
        <button
          className="text-sm ml-auto"
          style={{ color: "var(--color-navy)", opacity: 0.6 }}
          onClick={() => void load()}
        >
          ↻ Refresh
        </button>
      </div>

      {error && <p className="error-text mb-6">{error}</p>}

      <section className="mb-12">
        <h2 className="font-heading text-lg mb-4" style={{ color: "var(--color-navy)" }}>
          Settings
        </h2>
        <div
          className="rounded-lg border p-5"
          style={{ borderColor: "#ede8e0", backgroundColor: "#fff", maxWidth: 420 }}
        >
          <label className="block text-sm font-medium mb-1" style={{ color: "var(--color-navy)" }}>
            Initial credit grant for new users
          </label>
          <p className="text-xs mb-3" style={{ color: "var(--color-navy)", opacity: 0.5 }}>
            Credits automatically added when a new account is created.
          </p>
          {settings !== null && (
            <SettingsGrantRow
              value={settings.initial_credit_grant}
              onSave={async (v) => {
                const updated = await api.updateAdminSettings({ initial_credit_grant: v });
                setSettings(updated);
              }}
            />
          )}
        </div>
      </section>

      <section className="mb-12">
        <h2 className="font-heading text-lg mb-4" style={{ color: "var(--color-navy)" }}>
          Users &amp; balances
        </h2>
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "#ede8e0", backgroundColor: "#fff" }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: "#ede8e0" }}>
                <th className="p-3 font-medium">Email</th>
                <th className="p-3 font-medium">Balance</th>
                <th className="p-3 font-medium">Admin</th>
                <th className="p-3 font-medium">Adjust</th>
              </tr>
            </thead>
            <tbody>
              {users === null ? (
                <tr>
                  <td colSpan={4} className="p-4" style={{ opacity: 0.5 }}>
                    Loading…
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.user_id} className="border-t" style={{ borderColor: "#ede8e0" }}>
                    <td className="p-3">{u.email}</td>
                    <td className="p-3 font-medium">{u.balance}</td>
                    <td className="p-3">{u.is_admin ? "Yes" : "—"}</td>
                    <td className="p-3">
                      <AdjustRow
                        userId={u.user_id}
                        disabled={busyId === u.user_id}
                        onApply={(d) => void adjust(u.user_id, d)}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="font-heading text-lg mb-4" style={{ color: "var(--color-navy)" }}>
          Recent jobs
        </h2>
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "#ede8e0", backgroundColor: "#fff" }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: "#ede8e0" }}>
                <th className="p-3 font-medium whitespace-nowrap">Job</th>
                <th className="p-3 font-medium whitespace-nowrap">User</th>
                <th className="p-3 font-medium whitespace-nowrap">Mode</th>
                <th className="p-3 font-medium whitespace-nowrap">Lang</th>
                <th className="p-3 font-medium whitespace-nowrap">Tier</th>
                <th className="p-3 font-medium whitespace-nowrap">Credits est.</th>
                <th className="p-3 font-medium whitespace-nowrap">Words</th>
                <th className="p-3 font-medium whitespace-nowrap">Status</th>
                <th className="p-3 font-medium whitespace-nowrap">Progress</th>
                <th className="p-3 font-medium whitespace-nowrap">Updated</th>
              </tr>
            </thead>
            <tbody>
              {jobs === null ? (
                <tr>
                  <td colSpan={10} className="p-4" style={{ opacity: 0.5 }}>Loading…</td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-4" style={{ opacity: 0.5 }}>No jobs yet.</td>
                </tr>
              ) : (
                jobs.map((j) => (
                  <tr
                    key={j.job_id}
                    className="border-t cursor-pointer hover:bg-amber-50 transition-colors"
                    style={{ borderColor: "#ede8e0" }}
                    onClick={() => void openJobDetail(j.job_id)}
                  >
                    <td className="p-3 font-mono text-xs whitespace-nowrap">{j.job_id.slice(0, 8)}…</td>
                    <td className="p-3 whitespace-nowrap">{j.user_email}</td>
                    <td className="p-3 whitespace-nowrap">{j.mode}</td>
                    <td className="p-3 whitespace-nowrap">{j.target_language}</td>
                    <td className="p-3 whitespace-nowrap">{j.quality_tier ?? "—"}</td>
                    <td className="p-3 whitespace-nowrap">{j.credit_estimate ?? "—"}</td>
                    <td className="p-3 whitespace-nowrap">{j.word_count_estimate ?? "—"}</td>
                    <td className="p-3 whitespace-nowrap">
                      <StatusBadge status={j.status} />
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      {j.status === "processing" ? (
                        <span className="text-xs" style={{ color: "#1d4ed8" }}>
                          {j.progress_percent}%
                          {j.pipeline_stage && (
                            <span className="ml-1 opacity-60">{j.pipeline_stage}</span>
                          )}
                        </span>
                      ) : j.failure_class ? (
                        <span className="text-xs" style={{ color: "#991b1b" }}>{j.failure_class}</span>
                      ) : (
                        <span className="text-xs opacity-40">—</span>
                      )}
                    </td>
                    <td className="p-3 whitespace-nowrap text-xs opacity-60">
                      {new Date(j.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {(selectedJob || detailLoading) && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-16"
          style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
          onClick={() => setSelectedJob(null)}
        >
          <div
            className="relative rounded-xl shadow-xl p-6 w-full mx-4"
            style={{ backgroundColor: "#fff", maxWidth: 680, maxHeight: "85vh", overflowY: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="absolute top-4 right-4 text-sm opacity-40 hover:opacity-80"
              onClick={() => setSelectedJob(null)}
            >✕</button>

            {detailLoading ? (
              <p className="text-sm" style={{ opacity: 0.5 }}>Loading…</p>
            ) : selectedJob && (
              <>
                <h3 className="font-heading text-base mb-4" style={{ color: "var(--color-navy)" }}>
                  Job {selectedJob.job_id.slice(0, 8)}…
                </h3>

                <div className="mb-4">
                  <p className="text-xs font-medium uppercase mb-2" style={{ opacity: 0.5 }}>Cost</p>
                  <div className="grid grid-cols-3 gap-3">
                    <Stat label="Credits est." value={String(selectedJob.credit_estimate ?? "—")} />
                    <Stat label="USD cost" value={`$${selectedJob.total_cost_usd.toFixed(4)}`} />
                    <Stat label="Tokens in/out" value={`${selectedJob.total_tokens_in} / ${selectedJob.total_tokens_out}`} />
                  </div>
                </div>

                {selectedJob.run_info && (
                  <div className="mb-4">
                    <p className="text-xs font-medium uppercase mb-2" style={{ opacity: 0.5 }}>Current run</p>
                    <div
                      className="rounded-lg p-3 text-sm"
                      style={{ backgroundColor: "#f7f4ef" }}
                    >
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
                        <span style={{ opacity: 0.55 }}>Run ID</span>
                        <span className="font-mono">{selectedJob.run_info.job_run_id.slice(0, 12)}…</span>
                        <span style={{ opacity: 0.55 }}>Run status</span>
                        <span><StatusBadge status={selectedJob.run_info.run_status} /></span>
                        <span style={{ opacity: 0.55 }}>Worker</span>
                        <span className="font-mono">{selectedJob.run_info.worker_id ?? "—"}</span>
                        <span style={{ opacity: 0.55 }}>Heartbeat</span>
                        <span className={
                          selectedJob.run_info.heartbeat_at &&
                          Date.now() - new Date(selectedJob.run_info.heartbeat_at).getTime() > 10 * 60 * 1000
                            ? "text-red-600 font-medium"
                            : ""
                        }>
                          {heartbeatAge(selectedJob.run_info.heartbeat_at)}
                        </span>
                        <span style={{ opacity: 0.55 }}>Batches</span>
                        <span>
                          {selectedJob.run_info.completed_batches} / {selectedJob.run_info.total_batches} completed
                        </span>
                        <span style={{ opacity: 0.55 }}>Progress</span>
                        <span>{selectedJob.progress_percent}%{selectedJob.pipeline_stage ? ` · ${selectedJob.pipeline_stage}` : ""}</span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="mb-4">
                  <p className="text-xs font-medium uppercase mb-2" style={{ opacity: 0.5 }}>Parameters</p>
                  <table className="w-full text-sm">
                    <tbody>
                      <ParamRow label="Mode" value={selectedJob.mode} />
                      <ParamRow label="Target language" value={selectedJob.target_language} />
                      <ParamRow label="Source language" value={selectedJob.source_language_override ?? "auto"} />
                      <ParamRow label="Translation style" value={selectedJob.translation_style ?? "—"} />
                      <ParamRow label="User level" value={selectedJob.user_level ?? "—"} />
                      <ParamRow label="Explanation depth" value={selectedJob.explanation_depth ?? "—"} />
                      <ParamRow label="Quality tier" value={selectedJob.quality_tier ?? "—"} />
                      <ParamRow label="Word count est." value={String(selectedJob.word_count_estimate ?? "—")} />
                    </tbody>
                  </table>
                </div>

                <div>
                  <p className="text-xs font-medium uppercase mb-2" style={{ opacity: 0.5 }}>Meta</p>
                  <table className="w-full text-sm">
                    <tbody>
                      <ParamRow label="User" value={selectedJob.user_email} />
                      <ParamRow label="Status" value={selectedJob.status} />
                      <ParamRow label="Created" value={new Date(selectedJob.created_at).toLocaleString()} />
                      {selectedJob.processing_started_at && (
                        <ParamRow label="Started" value={new Date(selectedJob.processing_started_at).toLocaleString()} />
                      )}
                      <ParamRow label="Updated" value={new Date(selectedJob.updated_at).toLocaleString()} />
                      {selectedJob.failure_class && (
                        <ParamRow label="Failure class" value={selectedJob.failure_class} />
                      )}
                      {selectedJob.failure_reason && (
                        <tr className="border-t" style={{ borderColor: "#ede8e0" }}>
                          <td className="py-1.5 pr-3 text-xs align-top" style={{ opacity: 0.55, width: "30%" }}>Failure reason</td>
                          <td className="py-1.5 text-xs font-mono break-all" style={{ color: "#991b1b" }}>
                            {selectedJob.failure_reason}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SettingsGrantRow({
  value,
  onSave,
}: {
  value: number;
  onSave: (v: number) => Promise<void>;
}) {
  const [draft, setDraft] = useState(String(value));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const dirty = draft !== String(value);

  const save = async () => {
    const n = parseInt(draft, 10);
    if (!Number.isFinite(n) || n < 0) {
      setErr("Must be a non-negative integer.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await onSave(n);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3">
        <input
          type="number"
          min={0}
          className="rounded border px-3 py-1.5 text-sm w-28"
          style={{ borderColor: "#d4cfc8" }}
          value={draft}
          disabled={saving}
          onChange={(e) => { setDraft(e.target.value); setSaved(false); }}
        />
        <button
          type="button"
          className="btn-primary text-xs py-1.5 px-4"
          disabled={saving || !dirty}
          onClick={() => void save()}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {saved && (
          <span className="text-xs" style={{ color: "#2e7d32" }}>Saved ✓</span>
        )}
      </div>
      {err && <p className="error-text text-xs mt-1">{err}</p>}
    </div>
  );
}


function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg p-3 text-center" style={{ backgroundColor: "#f7f4ef" }}>
      <p className="text-xs mb-0.5" style={{ opacity: 0.5 }}>{label}</p>
      <p className="font-medium text-sm">{value}</p>
    </div>
  );
}

function ParamRow({ label, value }: { label: string; value: string }) {
  return (
    <tr className="border-t" style={{ borderColor: "#ede8e0" }}>
      <td className="py-1.5 pr-3 text-xs" style={{ opacity: 0.55, width: "30%" }}>{label}</td>
      <td className="py-1.5 text-sm font-medium">{value}</td>
    </tr>
  );
}

function AdjustRow({
  userId,
  disabled,
  onApply,
}: {
  userId: string;
  disabled: boolean;
  onApply: (delta: number) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="number"
        className="rounded border px-2 py-1 text-sm w-24"
        style={{ borderColor: "#ede8e0" }}
        placeholder="±credits"
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        aria-label={`Adjust credits for user ${userId}`}
      />
      <button
        type="button"
        className="btn-secondary text-xs py-1 px-2"
        disabled={disabled}
        onClick={() => {
          const n = parseInt(value, 10);
          if (!Number.isFinite(n) || n === 0) return;
          onApply(n);
          setValue("");
        }}
      >
        Apply
      </button>
    </div>
  );
}
