"use client";

import Script from "next/script";
import { useEffect } from "react";

const GA_ID = process.env.NEXT_PUBLIC_GA_ID || "";
const YM_ID = process.env.NEXT_PUBLIC_YM_ID || "";

function trackCTAClick(label: string) {
  if (typeof window !== "undefined") {
    if (window.gtag) {
      window.gtag("event", "cta_click", {
        event_category: "engagement",
        event_label: label,
      });
    }
    if (window.ym && YM_ID) {
      window.ym(Number(YM_ID), "reachGoal", "cta_click", { label });
    }
  }
}

export function setupCTATracking() {
  if (typeof window === "undefined") return;

  document.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    const link = target.closest("a");
    if (!link) return;

    const href = link.getAttribute("href") || "";
    if (href.includes("unfolda.ai")) {
      trackCTAClick("open_app");
    } else if (href.includes("apps.apple.com") || href.includes("App Store")) {
      trackCTAClick("app_store");
    } else if (
      href.includes("play.google.com") ||
      href.includes("Google Play")
    ) {
      trackCTAClick("google_play");
    }
  });
}

export function Analytics() {
  useEffect(() => {
    setupCTATracking();
  }, []);

  return (
    <>
      {GA_ID && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
            strategy="afterInteractive"
          />
          <Script id="gtag-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${GA_ID}');
            `}
          </Script>
        </>
      )}

      {YM_ID && (
        <Script id="yandex-metrika" strategy="afterInteractive">
          {`
            (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
            m[i].l=1*new Date();
            for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
            k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
            (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
            ym(${YM_ID}, "init", {
              clickmap:true,
              trackLinks:true,
              accurateTrackBounce:true,
              webvisor:true
            });
          `}
        </Script>
      )}
    </>
  );
}
