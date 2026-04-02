(function () {
  var STORAGE_KEYS = {
    lang: "unfolda_lang",
    theme: "unfolda_theme",
    noticeDismissed: "unfolda_notice_dismissed",
  };

  var SUPPORTED_LANGS = ["ru", "sr", "en", "es"];

  function safeGetStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function safeSetStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      // Ignore storage errors (privacy mode, blocked cookies, etc).
    }
  }

  function trackEvent(eventName, payload) {
    var eventPayload = Object.assign({ event: eventName }, payload || {});

    if (typeof window.gtag === "function" && window.UNFOLDA_GTAG_READY === true) {
      window.gtag("event", eventName, payload || {});
    }

    if (Array.isArray(window.dataLayer)) {
      window.dataLayer.push(eventPayload);
    }

    if (window.ym && typeof window.ym === "function" && window.YM_COUNTER_ID) {
      // Counter ID is intentionally external; this call keeps integration point ready.
      window.ym(window.YM_COUNTER_ID, "reachGoal", eventName, payload || {});
    }
  }

  function getGeoCountryCode() {
    // Placeholder hook for server-injected geo hint (window.UNFOLDA_GEO_COUNTRY).
    var geo = window.UNFOLDA_GEO_COUNTRY;
    if (typeof geo === "string") {
      return geo.trim().toUpperCase();
    }
    return "";
  }

  function mapGeoToLang(countryCode) {
    if (!countryCode) return null;
    if (countryCode === "RU") return "ru";
    if (["RS", "ME", "BA", "HR", "SI"].indexOf(countryCode) !== -1) return "sr";
    return null;
  }

  function mapBrowserToLang(browserLanguage) {
    var normalized = (browserLanguage || "").toLowerCase();
    if (normalized.indexOf("ru") === 0) return "ru";
    if (
      normalized.indexOf("sr") === 0 ||
      normalized.indexOf("hr") === 0 ||
      normalized.indexOf("bs") === 0 ||
      normalized.indexOf("sl") === 0
    ) {
      return "sr";
    }
    if (normalized.indexOf("es") === 0) return "es";
    return "en";
  }

  function detectLanguage() {
    var persisted = safeGetStorage(STORAGE_KEYS.lang);
    if (SUPPORTED_LANGS.indexOf(persisted) !== -1) {
      return { lang: persisted, source: "persisted" };
    }

    var geoLang = mapGeoToLang(getGeoCountryCode());
    if (geoLang) {
      return { lang: geoLang, source: "geo" };
    }

    return { lang: mapBrowserToLang(navigator.language), source: "browser" };
  }

  function getNestedValue(dictionary, keyPath) {
    var parts = keyPath.split(".");
    var current = dictionary;
    for (var i = 0; i < parts.length; i += 1) {
      if (!current || typeof current !== "object" || !(parts[i] in current)) {
        return null;
      }
      current = current[parts[i]];
    }
    return current;
  }

  function updateMetaTag(selector, attrName, value) {
    var element = document.querySelector(selector);
    if (!element || !value) return;
    element.setAttribute(attrName, value);
  }

  function applySeo(language) {
    var locales = window.UNFOLDA_LOCALES || {};
    var locale = locales[language] || locales.en;
    if (!locale || !locale.seo) return;

    document.documentElement.setAttribute("lang", language);
    document.title = locale.seo.title;
    updateMetaTag("#meta-description", "content", locale.seo.description);
    updateMetaTag("#meta-og-title", "content", locale.seo.ogTitle);
    updateMetaTag("#meta-og-description", "content", locale.seo.ogDescription);
    updateMetaTag("#meta-twitter-title", "content", locale.seo.twitterTitle);
    updateMetaTag("#meta-twitter-description", "content", locale.seo.twitterDescription);
  }

  function applyTranslations(language) {
    var locales = window.UNFOLDA_LOCALES || {};
    var activeLocale = locales[language] || locales.en;
    var fallbackLocale = locales.en || {};

    var nodes = document.querySelectorAll("[data-i18n]");
    nodes.forEach(function (node) {
      var key = node.getAttribute("data-i18n");
      var translated = getNestedValue(activeLocale, key);
      var fallback = getNestedValue(fallbackLocale, key);
      var value = translated || fallback;
      if (typeof value === "string") {
        node.textContent = value;
      }
    });

    applySeo(language);
    updateLangButtons(language);

    var langSwitcher = document.querySelector(".lang-switcher");
    var langAria =
      getNestedValue(activeLocale, "nav.languageSwitcherAria") ||
      getNestedValue(fallbackLocale, "nav.languageSwitcherAria");
    if (langSwitcher && langAria) {
      langSwitcher.setAttribute("aria-label", langAria);
    }
  }

  function updateLangButtons(language) {
    var buttons = document.querySelectorAll(".lang-btn");
    buttons.forEach(function (button) {
      var isActive = button.getAttribute("data-lang") === language;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function applyTheme(theme) {
    var normalized = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", normalized);

    var toggle = document.getElementById("theme-toggle");
    if (toggle) {
      var locales = window.UNFOLDA_LOCALES || {};
      var language = document.documentElement.getAttribute("lang") || "en";
      var locale = locales[language] || locales.en || {};
      var darkLabel = getNestedValue(locale, "nav.themeDark") || "Dark";
      var lightLabel = getNestedValue(locale, "nav.themeLight") || "Light";
      var label = normalized === "dark" ? lightLabel : darkLabel;
      var labelNode = toggle.querySelector("[data-i18n='nav.themeDark']");
      if (!labelNode) {
        labelNode = document.createElement("span");
        labelNode.setAttribute("data-i18n", "nav.themeDark");
        toggle.textContent = "";
        toggle.appendChild(labelNode);
      }
      labelNode.textContent = label;
      toggle.setAttribute("aria-label", label);
    }
  }

  function scrollToTopWithOffset() {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  function showLanguageNoticeIfNeeded(source, language) {
    var notice = document.getElementById("language-notice");
    if (!notice) return;

    var manuallyChosen = safeGetStorage(STORAGE_KEYS.lang);
    var dismissed = safeGetStorage(STORAGE_KEYS.noticeDismissed);
    if (manuallyChosen || dismissed === "1") return;
    if (source !== "geo" && source !== "browser") return;

    notice.classList.remove("is-hidden");
    var changeButton = document.getElementById("notice-change");
    var dismissButton = document.getElementById("notice-dismiss");

    if (changeButton) {
      changeButton.addEventListener("click", function () {
        scrollToTopWithOffset();
        var activeButton = document.querySelector(".lang-btn.is-active") || document.querySelector(".lang-btn");
        if (activeButton && typeof activeButton.focus === "function") {
          activeButton.focus();
        }
        trackEvent("language_notice_action", { action: "change", lang: language });
      });
    }

    if (dismissButton) {
      dismissButton.addEventListener("click", function () {
        safeSetStorage(STORAGE_KEYS.noticeDismissed, "1");
        notice.classList.add("is-hidden");
        trackEvent("language_notice_action", { action: "dismiss", lang: language });
      });
    }
  }

  function setupFaqTracking() {
    var faqItems = document.querySelectorAll(".faq-item");
    faqItems.forEach(function (item) {
      item.addEventListener("toggle", function () {
        if (item.open) {
          trackEvent("faq_open", {
            faq_id: item.getAttribute("data-faq-id") || "unknown",
            lang: document.documentElement.getAttribute("lang") || "en",
          });
        }
      });
    });
  }

  function setupCtaTracking() {
    var trackedNodes = document.querySelectorAll("[data-track]");
    trackedNodes.forEach(function (node) {
      node.addEventListener("click", function () {
        trackEvent(node.getAttribute("data-track"), {
          lang: document.documentElement.getAttribute("lang") || "en",
          theme: document.documentElement.getAttribute("data-theme") || "dark",
        });
      });
    });
  }

  function initializeTheme() {
    var persistedTheme = safeGetStorage(STORAGE_KEYS.theme);
    applyTheme(persistedTheme === "light" ? "light" : "dark");

    var themeToggle = document.getElementById("theme-toggle");
    if (!themeToggle) return;

    themeToggle.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme");
      var nextTheme = current === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      safeSetStorage(STORAGE_KEYS.theme, nextTheme);
      trackEvent("theme_switch", {
        next_theme: nextTheme,
        lang: document.documentElement.getAttribute("lang") || "en",
      });
    });
  }

  function initializeLanguage() {
    var detected = detectLanguage();
    applyTranslations(detected.lang);

    var buttons = document.querySelectorAll(".lang-btn");
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var selected = button.getAttribute("data-lang");
        if (SUPPORTED_LANGS.indexOf(selected) === -1) return;
        var previous = document.documentElement.getAttribute("lang") || "en";
        applyTranslations(selected);
        applyTheme(document.documentElement.getAttribute("data-theme"));
        safeSetStorage(STORAGE_KEYS.lang, selected);
        trackEvent("language_switch", {
          from: previous,
          to: selected,
        });
      });
    });

    showLanguageNoticeIfNeeded(detected.source, detected.lang);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initializeLanguage();
    initializeTheme();
    setupCtaTracking();
    setupFaqTracking();
  });
})();
