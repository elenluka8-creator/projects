(function () {
  "use strict";

  const STORAGE_LANG_KEY = "unfolda_lang";
  const STORAGE_THEME_KEY = "unfolda_theme";
  const CTA_URL = "https://unfolda.ai";

  let currentLang = DEFAULT_LANG;
  let detectedLang = null;

  /* ============================================
     LANGUAGE DETECTION
     ============================================ */

  function getStoredLang() {
    try {
      const stored = localStorage.getItem(STORAGE_LANG_KEY);
      if (stored && SUPPORTED_LANGS.includes(stored)) return stored;
    } catch (_) {}
    return null;
  }

  function setStoredLang(lang) {
    try {
      localStorage.setItem(STORAGE_LANG_KEY, lang);
    } catch (_) {}
  }

  function detectGeoLang() {
    return new Promise(function (resolve) {
      var timeout = setTimeout(function () { resolve(null); }, 3000);

      fetch("https://ipapi.co/json/", { mode: "cors" })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          clearTimeout(timeout);
          var country = (data.country_code || "").toUpperCase();
          resolve(LANG_GEO_MAP[country] || null);
        })
        .catch(function () {
          clearTimeout(timeout);
          resolve(null);
        });
    });
  }

  function detectBrowserLang() {
    try {
      var navLangs = navigator.languages || [navigator.language || navigator.userLanguage || ""];
      for (var i = 0; i < navLangs.length; i++) {
        var code = navLangs[i].toLowerCase().split("-")[0];
        if (BROWSER_LANG_MAP[code]) return BROWSER_LANG_MAP[code];
        if (SUPPORTED_LANGS.indexOf(code) !== -1) return code;
      }
    } catch (_) {}
    return DEFAULT_LANG;
  }

  async function resolveLanguage() {
    var stored = getStoredLang();
    if (stored) return { lang: stored, source: "stored" };

    var geo = await detectGeoLang();
    if (geo) return { lang: geo, source: "geo" };

    var browser = detectBrowserLang();
    return { lang: browser, source: "browser" };
  }

  /* ============================================
     i18n APPLICATION
     ============================================ */

  function getNestedValue(obj, path) {
    return path.split(".").reduce(function (o, k) {
      return o && o[k];
    }, obj);
  }

  function applyLocale(lang) {
    var locale = LOCALES[lang];
    if (!locale) return;

    currentLang = lang;
    document.documentElement.lang = lang;

    var els = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < els.length; i++) {
      var key = els[i].getAttribute("data-i18n");
      var value = getNestedValue(locale, key);
      if (value) els[i].textContent = value;
    }

    updateMeta(locale);
    updateLangSwitcher(lang);
    setStoredLang(lang);
  }

  function updateMeta(locale) {
    document.title = locale.meta.title;

    var setMeta = function (selector, attr, value) {
      var el = document.querySelector(selector);
      if (el) el.setAttribute(attr, value);
    };

    setMeta('meta[name="description"]', "content", locale.meta.description);
    setMeta('meta[property="og:title"]', "content", locale.meta.title);
    setMeta('meta[property="og:description"]', "content", locale.meta.description);
    setMeta('meta[name="twitter:title"]', "content", locale.meta.title);
    setMeta('meta[name="twitter:description"]', "content", locale.meta.description);
  }

  function updateLangSwitcher(lang) {
    var btns = document.querySelectorAll(".lang-switcher__btn");
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle("active", btns[i].getAttribute("data-lang") === lang);
    }
  }

  /* ============================================
     THEME SYSTEM
     ============================================ */

  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_THEME_KEY);
    } catch (_) {}
    return null;
  }

  function setStoredTheme(theme) {
    try {
      localStorage.setItem(STORAGE_THEME_KEY, theme);
    } catch (_) {}
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var icon = document.querySelector(".theme-toggle__icon");
    if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
    setStoredTheme(theme);
  }

  function getCurrentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function initTheme() {
    var stored = getStoredTheme();
    if (stored === "dark" || stored === "light") {
      applyTheme(stored);
      return;
    }
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      applyTheme("dark");
    } else {
      applyTheme("light");
    }
  }

  /* ============================================
     ANALYTICS TRACKING
     ============================================ */

  function trackEvent(eventName, params) {
    params = params || {};

    if (typeof gtag === "function") {
      gtag("event", eventName, params);
    }

    if (typeof ym === "function") {
      ym(0, "reachGoal", eventName, params);
    }
  }

  /* ============================================
     FAQ ACCORDION
     ============================================ */

  function initFaq() {
    var questions = document.querySelectorAll(".faq-item__question");
    for (var i = 0; i < questions.length; i++) {
      questions[i].addEventListener("click", function () {
        var item = this.closest(".faq-item");
        var isOpen = item.classList.contains("open");

        var allItems = document.querySelectorAll(".faq-item");
        for (var j = 0; j < allItems.length; j++) {
          allItems[j].classList.remove("open");
          allItems[j].querySelector(".faq-item__question").setAttribute("aria-expanded", "false");
        }

        if (!isOpen) {
          item.classList.add("open");
          this.setAttribute("aria-expanded", "true");
          trackEvent("faq_open", {
            question: this.querySelector("[data-i18n]").getAttribute("data-i18n")
          });
        }
      });
    }
  }

  /* ============================================
     STICKY CTA
     ============================================ */

  function initStickyCta() {
    var stickyCta = document.getElementById("stickyCta");
    if (!stickyCta) return;

    var hero = document.getElementById("hero");
    if (!hero) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            stickyCta.classList.remove("visible");
            stickyCta.setAttribute("aria-hidden", "true");
          } else {
            if (window.innerWidth < 768) {
              stickyCta.classList.add("visible");
              stickyCta.setAttribute("aria-hidden", "false");
            }
          }
        });
      },
      { threshold: 0.1 }
    );

    observer.observe(hero);

    window.addEventListener("resize", function () {
      if (window.innerWidth >= 768) {
        stickyCta.classList.remove("visible");
        stickyCta.setAttribute("aria-hidden", "true");
      }
    });
  }

  /* ============================================
     SCROLL ANIMATIONS
     ============================================ */

  function initScrollAnimations() {
    if (!("IntersectionObserver" in window)) {
      var fadeEls = document.querySelectorAll(".fade-in");
      for (var i = 0; i < fadeEls.length; i++) {
        fadeEls[i].classList.add("visible");
      }
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
    );

    var fadeEls = document.querySelectorAll(".fade-in");
    for (var i = 0; i < fadeEls.length; i++) {
      observer.observe(fadeEls[i]);
    }
  }

  /* ============================================
     LANGUAGE NOTICE
     ============================================ */

  function showLangNotice(suggestedLang) {
    if (!suggestedLang || suggestedLang === currentLang) return;

    detectedLang = suggestedLang;

    var notice = document.getElementById("langNotice");
    var changeBtn = document.getElementById("langNoticeChange");
    var dismissBtn = document.getElementById("langNoticeDismiss");

    if (!notice || !changeBtn || !dismissBtn) return;

    var suggestedLocale = LOCALES[suggestedLang];
    if (!suggestedLocale) return;

    var textEl = document.getElementById("langNoticeText");
    if (textEl) textEl.textContent = suggestedLocale.langNotice.text;
    changeBtn.textContent = suggestedLocale.langNotice.change;
    dismissBtn.textContent = suggestedLocale.langNotice.dismiss;

    notice.classList.add("visible");
    notice.setAttribute("aria-hidden", "false");

    changeBtn.onclick = function () {
      applyLocale(suggestedLang);
      notice.classList.remove("visible");
      notice.setAttribute("aria-hidden", "true");
      trackEvent("lang_notice_change", { to_lang: suggestedLang });
    };

    dismissBtn.onclick = function () {
      notice.classList.remove("visible");
      notice.setAttribute("aria-hidden", "true");
      trackEvent("lang_notice_dismiss", { suggested_lang: suggestedLang });
    };
  }

  /* ============================================
     EVENT LISTENERS
     ============================================ */

  function initEventListeners() {
    var langBtns = document.querySelectorAll(".lang-switcher__btn");
    for (var i = 0; i < langBtns.length; i++) {
      langBtns[i].addEventListener("click", function () {
        var lang = this.getAttribute("data-lang");
        if (lang && lang !== currentLang) {
          applyLocale(lang);
          trackEvent("language_switch", { to_lang: lang });

          var notice = document.getElementById("langNotice");
          if (notice) {
            notice.classList.remove("visible");
            notice.setAttribute("aria-hidden", "true");
          }
        }
      });
    }

    var themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", function () {
        var newTheme = getCurrentTheme() === "dark" ? "light" : "dark";
        applyTheme(newTheme);
        trackEvent("theme_switch", { theme: newTheme });
      });
    }

    document.addEventListener("click", function (e) {
      var tracked = e.target.closest("[data-track]");
      if (tracked) {
        var eventName = tracked.getAttribute("data-track");
        trackEvent(eventName, { lang: currentLang });
      }
    });

    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener("click", function (e) {
        var target = document.querySelector(this.getAttribute("href"));
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  /* ============================================
     INITIALIZATION
     ============================================ */

  async function init() {
    initTheme();

    var browserLang = detectBrowserLang();
    applyLocale(browserLang);

    initFaq();
    initStickyCta();
    initScrollAnimations();
    initEventListeners();

    var result = await resolveLanguage();

    if (result.lang !== currentLang) {
      if (result.source === "stored") {
        applyLocale(result.lang);
      } else {
        showLangNotice(result.lang);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
