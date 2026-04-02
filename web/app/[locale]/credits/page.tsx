"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";

type Row = {
  transaction_id: string;
  type: string;
  amount: number;
  balance_after: number;
  created_at: string;
  job_id: string | null;
};

export default function CreditsHistoryPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/backend/credits/history", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as Row[];
        if (!cancelled) {
          setRows(Array.isArray(data) ? data : []);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load history");
          setRows(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <h1
        className="font-heading text-2xl mb-8"
        style={{ color: "var(--color-navy)" }}
      >
        Credit history
      </h1>

      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}

      {rows === null && !error && <p>Loading…</p>}

      {rows !== null && (
        <table style={{ borderCollapse: "collapse", width: "100%", maxWidth: "56rem" }}>
          <thead>
            <tr>
              {["Type", "Amount", "Balance after", "Date", "Job"].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: "left",
                    borderBottom: "1px solid #ccc",
                    paddingBottom: "0.4rem",
                    paddingRight: "1.5rem",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ paddingTop: "1rem", opacity: 0.6 }}>
                  No transactions yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.transaction_id}>
                  <td style={{ padding: "0.4rem 1.5rem 0.4rem 0" }}>{r.type}</td>
                  <td style={{ paddingRight: "1.5rem" }}>
                    {r.amount > 0 ? `+${r.amount}` : r.amount}
                  </td>
                  <td style={{ paddingRight: "1.5rem" }}>{r.balance_after}</td>
                  <td style={{ paddingRight: "1.5rem" }}>
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td>
                    {r.job_id ? (
                      <a href={`/jobs/${r.job_id}`}>{r.job_id.slice(0, 8)}…</a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}
