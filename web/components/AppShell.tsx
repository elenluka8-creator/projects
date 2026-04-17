"use client";

import type { ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Container } from "./Container";
import { HeaderBar } from "./HeaderBar";
import { LocaleSwitcher } from "./LocaleSwitcher";

type AppShellProps = {
  children: ReactNode;
};

/**
 * Page shell with a minimal top bar and centred content area.
 *
 * Keeps navigation intentionally minimal — the brand identity is
 * expressed through typography and the cream/navy palette, not broker.
 */
export function AppShell({ children }: AppShellProps) {
  const locale = useLocale();
  const t = useTranslations("nav");

  return (
    <div className="flex min-h-screen flex-col" style={{ backgroundColor: "var(--color-cream)" }}>
      <header
        className="border-b py-5"
        style={{ borderColor: "#ede8e0", backgroundColor: "var(--color-cream)" }}
      >
        <Container>
          <div className="flex items-center gap-6">
            <a href={`/${locale}/jobs`} aria-label="Unfolda — home" style={{ display: "block", lineHeight: 0 }}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 250 58"
                aria-hidden="true"
                focusable="false"
                style={{ height: 38, width: "auto", display: "block" }}
              >
                <path d="M8 6 Q8 2 12 2 L30 2 L30 56 L10 56 Q6 56 6 52 L6 10 Q6 6 8 6 Z" fill="#1a1f36"/>
                <path d="M32 2 L52 2 Q56 2 56 6 L56 52 Q56 56 52 56 L32 56 Z" fill="#c9963a"/>
                <line x1="31" y1="0" x2="31" y2="58" stroke="#0f1219" strokeWidth="2.5" strokeLinecap="round"/>
                <line x1="13" y1="18" x2="25" y2="18" stroke="#faf6ef" strokeWidth="2" strokeLinecap="round" opacity="0.35"/>
                <line x1="13" y1="26" x2="24" y2="26" stroke="#faf6ef" strokeWidth="2" strokeLinecap="round" opacity="0.25"/>
                <line x1="13" y1="34" x2="25" y2="34" stroke="#faf6ef" strokeWidth="2" strokeLinecap="round" opacity="0.18"/>
                <line x1="37" y1="18" x2="50" y2="18" stroke="#1a1f36" strokeWidth="2" strokeLinecap="round" opacity="0.22"/>
                <line x1="37" y1="26" x2="49" y2="26" stroke="#1a1f36" strokeWidth="2" strokeLinecap="round" opacity="0.16"/>
                <line x1="37" y1="34" x2="50" y2="34" stroke="#1a1f36" strokeWidth="2" strokeLinecap="round" opacity="0.12"/>
                <text x="72" y="42" fontFamily="Inter, system-ui, sans-serif" fontWeight="600" fontSize="34" fill="#1a1f36" letterSpacing="-0.5">Unfolda</text>
              </svg>
            </a>
            <nav className="flex items-center gap-5" aria-label="Main navigation">
              <a
                href={`/${locale}/jobs`}
                className="text-sm"
                style={{ color: "var(--color-navy)", opacity: 0.7 }}
              >
                {t("jobs")}
              </a>
            </nav>
            <div className="ml-auto flex items-center gap-3">
              <LocaleSwitcher />
              <HeaderBar />
            </div>
          </div>
        </Container>
      </header>

      <main className="flex-1 py-10">
        <Container>{children}</Container>
      </main>

      <footer
        className="border-t py-6 text-sm"
        style={{
          borderColor: "#ede8e0",
          color: "var(--color-navy)",
        }}
      >
        <Container>
          <div className="flex items-center justify-between flex-wrap gap-3" style={{ opacity: 0.5 }}>
            <p>Unfolda &mdash; {t("footer")}</p>
            <nav className="flex items-center gap-4" aria-label="Legal">
              <a
                href={`/${locale}/terms`}
                style={{ color: "var(--color-navy)" }}
                className="hover:opacity-100 transition-opacity"
              >
                {t("terms")}
              </a>
              <a
                href={`/${locale}/privacy`}
                style={{ color: "var(--color-navy)" }}
                className="hover:opacity-100 transition-opacity"
              >
                {t("privacy")}
              </a>
            </nav>
          </div>
        </Container>
      </footer>
    </div>
  );
}
