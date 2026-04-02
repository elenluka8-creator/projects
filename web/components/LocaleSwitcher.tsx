"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { routing } from "@/i18n/routing";

const LOCALE_LABELS: Record<string, string> = {
  en: "EN",
  ru: "RU",
  sr: "SR",
  es: "ES",
};

export function LocaleSwitcher() {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  const switchLocale = (next: string) => {
    if (next === locale) return;
    const localePrefix = `/${locale}`;
    const rest = pathname.startsWith(localePrefix)
      ? pathname.slice(localePrefix.length) || "/"
      : pathname;
    router.push(`/${next}${rest}`);
  };

  return (
    <div className="flex items-center gap-1">
      {routing.locales.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => switchLocale(l)}
          className="rounded px-1.5 py-0.5 text-xs font-medium transition-colors"
          style={{
            color: l === locale ? "var(--color-navy)" : "var(--color-navy)",
            opacity: l === locale ? 1 : 0.4,
            backgroundColor: l === locale ? "rgba(26,31,54,0.08)" : "transparent",
          }}
          aria-current={l === locale ? "true" : undefined}
        >
          {LOCALE_LABELS[l] ?? l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
