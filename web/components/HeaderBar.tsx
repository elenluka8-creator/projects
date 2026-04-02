"use client";

import { useEffect, useState } from "react";
import { signOut } from "next-auth/react";
import { useTranslations } from "next-intl";

type CreditsPayload = { balance: number };

export function HeaderBar() {
  const [balance, setBalance] = useState<number | null>(null);
  const t = useTranslations("nav");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/backend/config/credits", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as CreditsPayload;
        if (!cancelled && typeof data.balance === "number") {
          setBalance(data.balance);
        }
      } catch {
        // silently ignore — balance stays null (shown as "…")
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex items-center gap-3">
      <span
        data-testid="header-credits"
        className="text-sm"
        style={{ color: "var(--color-navy)", opacity: 0.75 }}
      >
        {t("creditsBalance", { balance: balance ?? "…" })}
      </span>
      <button
        type="button"
        aria-label={t("signOut")}
        title={t("signOut")}
        onClick={() => signOut({ callbackUrl: "/en/login" })}
        style={{
          color: "var(--color-navy)",
          opacity: 0.45,
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "4px",
          display: "flex",
          alignItems: "center",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.9"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.45"; }}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10 11l3-3-3-3M13 8H6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
