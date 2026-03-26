(() => {
  "use strict";

  const METRIKA_COUNTER_ID = 0;
  const TEXTS = window.UnfoldaLocales || {};
  const DEFAULT_LANG = "en";
  const LANGUAGE_NOTICE_DISMISSED_KEY = "unfolda_lang_notice_dismissed";

  const COUNTRY_LANG_MAP = {
    RU: "ru",
    RS: "sr",
    ME: "sr",
    BA: "sr",
    HR: "sr",
    SI: "sr",
  };

  const BROWSER_LANG_MAP = {
    ru: "ru",
    sr: "sr",
    hr: "sr",
    bs: "sr",
    sl: "sr",
    es: "es",
    en: "en",
  };

  const trackEvent = (eventName, params = {}) => {
    if (typeof window.gtag === "function") {
      window.gtag("event", eventName, params);
    }
    if (typeof window.ym === "function" && METRIKA_COUNTER_ID > 0) {
      window.ym(METRIKA_COUNTER_ID, "reachGoal", eventName);
    }
  };

  const setMeta = (lang) => {
    const bundle = TEXTS[lang] || TEXTS[DEFAULT_LANG];
    if (!bundle) return;

    document.title = bundle.meta_title;
    const desc = document.querySelector('meta[name="description"]');
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const ogDesc = document.querySelector('meta[property="og:description"]');
    const twTitle = document.querySelector('meta[name="twitter:title"]');
    const twDesc = document.querySelector('meta[name="twitter:description"]');

    if (desc) desc.setAttribute("content", bundle.meta_description);
    if (ogTitle) ogTitle.setAttribute("content", bundle.meta_og_title);
    if (ogDesc) ogDesc.setAttribute("content", bundle.meta_og_description);
    if (twTitle) twTitle.setAttribute("content", bundle.meta_og_title);
    if (twDesc) twDesc.setAttribute("content", bundle.meta_og_description);
  };

  const updateThemeToggleText = () => {
    const currentLang = document.documentElement.lang || DEFAULT_LANG;
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const bundle = TEXTS[currentLang] || TEXTS[DEFAULT_LANG];
    const themeButton = document.getElementById("themeToggle");
    if (!themeButton || !bundle) return;
    themeButton.textContent = currentTheme === "dark" ? bundle.theme_toggle_dark : bundle.theme_toggle_light;
  };

  const applyLanguage = (lang, options = {}) => {
    const shouldPersist = options.shouldPersist !== false;
    const source = options.source || "manual";
    const showTooltip = Boolean(options.showTooltip);
    const bundle = TEXTS[lang] || TEXTS[DEFAULT_LANG];
    if (!bundle) return;

    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key && Object.prototype.hasOwnProperty.call(bundle, key)) {
        el.textContent = bundle[key];
      }
    });

    setMeta(lang);

    document.querySelectorAll(".js-lang").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.dataset.lang === lang));
    });

    if (shouldPersist) {
      localStorage.setItem("unfolda_lang", lang);
    }

    updateThemeToggleText();
    updateLanguageNotice(source, lang, showTooltip);
  };

  const updateLanguageNotice = (source, lang, showRequested) => {
    const notice = document.getElementById("langNotice");
    const text = document.getElementById("langNoticeText");
    if (!notice || !text) return;

    const dismissed = localStorage.getItem(LANGUAGE_NOTICE_DISMISSED_KEY) === "1";
    const bundle = TEXTS[document.documentElement.lang] || TEXTS[DEFAULT_LANG];
    if (!bundle) return;

    const messageKey =
      source === "geo"
        ? `lang_notice_geo_${lang}`
        : source === "browser"
          ? `lang_notice_browser_${lang}`
          : "lang_notice_unknown_en";

    text.textContent = bundle[messageKey] || bundle.lang_notice_unknown_en || "";

    const shouldShow = showRequested && !dismissed && (source === "geo" || source === "browser");
    notice.hidden = !shouldShow;
  };

  const applyTheme = (theme, shouldPersist = true) => {
    const resolvedTheme = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", resolvedTheme);

    const themeButton = document.getElementById("themeToggle");
    if (themeButton) {
      themeButton.setAttribute("aria-pressed", String(resolvedTheme === "light"));
    }

    if (shouldPersist) {
      localStorage.setItem("unfolda_theme", resolvedTheme);
    }

    updateThemeToggleText();
  };

  const normalizeBrowserLanguage = () => {
    const raw = (navigator.language || DEFAULT_LANG).toLowerCase().split("-")[0];
    return BROWSER_LANG_MAP[raw] || DEFAULT_LANG;
  };

  const detectCountryCode = async () => {
    try {
      const response = await fetch("https://ipapi.co/json/");
      if (!response.ok) return null;
      const data = await response.json();
      if (data && typeof data.country_code === "string") {
        return data.country_code.toUpperCase();
      }
    } catch (_error) {
      // Silent fallback to browser language.
    }
    return null;
  };

  const detectInitialLanguage = async () => {
    const persisted = localStorage.getItem("unfolda_lang");
    if (persisted && TEXTS[persisted]) {
      return { lang: persisted, source: "persisted", showTooltip: false };
    }

    const countryCode = await detectCountryCode();
    if (countryCode && COUNTRY_LANG_MAP[countryCode]) {
      return { lang: COUNTRY_LANG_MAP[countryCode], source: "geo", showTooltip: true };
    }

    // For all other countries or unavailable geo, use browser preference.
    return { lang: normalizeBrowserLanguage(), source: "browser", showTooltip: true };
  };

  const initHandlers = () => {
    document.querySelectorAll(".js-track").forEach((element) => {
      element.addEventListener("click", () => {
        const name = element.getAttribute("data-track") || "cta_click";
        trackEvent(name, {
          link_text: element.textContent ? element.textContent.trim() : "",
          link_url: element.getAttribute("href") || "",
        });
      });
    });

    document.querySelectorAll(".js-lang").forEach((button) => {
      button.addEventListener("click", () => {
        const selectedLang = button.dataset.lang || DEFAULT_LANG;
        applyLanguage(selectedLang, { source: "manual", showTooltip: false });
        const notice = document.getElementById("langNotice");
        if (notice) {
          notice.hidden = true;
        }
        trackEvent("language_switch", { language: selectedLang });
      });
    });

    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        trackEvent("theme_switch", { theme: next });
      });
    }

    const notice = document.getElementById("langNotice");
    const dismissButton = document.querySelector(".js-lang-dismiss");
    const openButton = document.querySelector(".js-lang-open");
    const switcher = document.getElementById("languageSwitcher");

    if (dismissButton && notice) {
      dismissButton.addEventListener("click", () => {
        notice.hidden = true;
        localStorage.setItem(LANGUAGE_NOTICE_DISMISSED_KEY, "1");
      });
    }

    if (openButton && switcher) {
      openButton.addEventListener("click", () => {
        switcher.scrollIntoView({ behavior: "smooth", block: "center" });
        switcher.classList.add("switcher-highlight");
        window.setTimeout(() => {
          switcher.classList.remove("switcher-highlight");
        }, 1200);
      });
    }

    // Track FAQ open interactions for conversion insight.
    document.querySelectorAll(".faq-item").forEach((item, index) => {
      item.addEventListener("toggle", () => {
        if (item.open) {
          trackEvent("faq_open", { faq_index: index + 1 });
        }
      });
    });
  };

  const initAnimations = () => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("show");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );

    document.querySelectorAll(".fade-in").forEach((el) => observer.observe(el));
  };

  const initTheme = () => {
    const persistedTheme = localStorage.getItem("unfolda_theme");
    const systemPrefersLight =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: light)").matches;
    applyTheme(persistedTheme || (systemPrefersLight ? "light" : "dark"), false);
  };

  const init = async () => {
    initHandlers();
    initTheme();

    const initialLanguage = await detectInitialLanguage();
    applyLanguage(initialLanguage.lang, {
      shouldPersist: false,
      source: initialLanguage.source,
      showTooltip: initialLanguage.showTooltip,
    });

    const yearNode = document.getElementById("year");
    if (yearNode) {
      yearNode.textContent = String(new Date().getFullYear());
    }

    initAnimations();
  };

  init();
})();
