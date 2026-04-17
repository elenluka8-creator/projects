"use client";

import { signIn } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";

function GoogleIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      aria-hidden="true"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
        fill="#4285F4"
      />
      <path
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"
        fill="#34A853"
      />
      <path
        d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
        fill="#FBBC05"
      />
      <path
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"
        fill="#EA4335"
      />
    </svg>
  );
}

export default function LoginPage() {
  const t = useTranslations("login");
  const locale = useLocale();

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{ backgroundColor: "var(--color-cream)" }}
    >
      <div className="w-full max-w-sm">
        <div className="mb-10 text-center">
          <h1
            className="font-heading text-4xl"
            style={{ color: "var(--color-navy)" }}
          >
            Unfolda
          </h1>
          <p
            className="mt-2 text-sm"
            style={{ color: "var(--color-navy)", opacity: 0.6 }}
          >
            {t("tagline")}
          </p>
        </div>

        <div className="card">
          <p
            className="mb-6 text-sm leading-relaxed"
            style={{ color: "var(--color-navy)", opacity: 0.75 }}
          >
            {t("description")}
          </p>

          <button
            type="button"
            onClick={() => signIn("google", { callbackUrl: `/${locale}/jobs` })}
            className="flex w-full items-center justify-center gap-3 rounded border px-5 py-3 text-sm font-medium transition-colors"
            style={{
              borderColor: "#d4cfc8",
              backgroundColor: "#fff",
              color: "var(--color-navy)",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                "var(--color-navy)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                "#d4cfc8";
            }}
          >
            <GoogleIcon />
            {t("signIn")}
          </button>

          <p className="mt-4 text-center text-xs" style={{ color: "var(--color-navy)", opacity: 0.55 }}>
            {t("tosNote")}{" "}
            <a href={`/${locale}/terms`} className="underline" style={{ color: "var(--color-navy)" }}>
              {t("tosLink")}
            </a>
            {" "}&amp;{" "}
            <a href={`/${locale}/privacy`} className="underline" style={{ color: "var(--color-navy)" }}>
              {t("privacyLink")}
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
