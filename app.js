// Unfolda Landing — App Logic v1.0.0
// Language detection, theme switching, FAQ, analytics, scroll reveal
'use strict';

/* ============================================================
   CONSTANTS
   ============================================================ */
const APP_URL = 'https://unfolda.ai';
const SUPPORTED_LANGS = ['en', 'es', 'sr', 'ru'];
const STORAGE_LANG_KEY = 'unfolda_lang';
const STORAGE_THEME_KEY = 'unfolda_theme';

// Geo-country to language mapping
const GEO_LANG_MAP = {
  RU: 'ru',
  RS: 'sr', ME: 'sr', BA: 'sr', HR: 'sr', SI: 'sr',
};

// Browser language prefix to UI language mapping
const BROWSER_LANG_MAP = {
  ru: 'ru',
  sr: 'sr', hr: 'sr', bs: 'sr', sl: 'sr',
  es: 'es',
};

/* ============================================================
   LANGUAGE DETECTION
   ============================================================ */
function resolveLanguage() {
  // 1. Persisted user choice
  const saved = localStorage.getItem(STORAGE_LANG_KEY);
  if (saved && SUPPORTED_LANGS.includes(saved)) return saved;

  // 2. Browser language fallback (geo detection requires a server; we use browser only in static context)
  const browserLang = (navigator.language || navigator.userLanguage || 'en').split('-')[0].toLowerCase();
  const mapped = BROWSER_LANG_MAP[browserLang];
  if (mapped) return mapped;

  return 'en';
}

/* ============================================================
   ANALYTICS HELPERS
   ============================================================ */
function trackEvent(name, params) {
  try {
    if (window.gtag) {
      window.gtag('event', name, params || {});
    }
    if (window.ym && window._ym_uid) {
      window.ym(window._ym_uid, 'reachGoal', name, params || {});
    }
  } catch (e) { /* analytics should never crash the page */ }
}

/* ============================================================
   THEME SYSTEM
   ============================================================ */
function getStoredTheme() {
  return localStorage.getItem(STORAGE_THEME_KEY) || 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_THEME_KEY, theme);

  const sunIcon = document.getElementById('icon-sun');
  const moonIcon = document.getElementById('icon-moon');
  if (sunIcon && moonIcon) {
    sunIcon.style.display = theme === 'dark' ? 'block' : 'none';
    moonIcon.style.display = theme === 'dark' ? 'none' : 'block';
  }
}

function initTheme() {
  const stored = getStoredTheme();
  applyTheme(stored);

  const toggleBtn = document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  toggleBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    trackEvent('theme_switch', { theme: next });
  });
}

/* ============================================================
   i18n — DOM RENDERING
   ============================================================ */
function renderLang(lang) {
  const t = LOCALES[lang];
  if (!t) return;

  // <html> lang attribute + dir
  document.documentElement.lang = t.meta.lang;
  document.documentElement.dir = t.meta.dir || 'ltr';

  // Meta tags
  setMeta('title', t.meta.title);
  setMeta('description', t.meta.description);
  setMeta('og:title', t.meta.ogTitle);
  setMeta('og:description', t.meta.ogDescription);
  setMeta('twitter:title', t.meta.ogTitle);
  setMeta('twitter:description', t.meta.ogDescription);

  // All elements with data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const val = getNestedKey(t, key);
    if (val !== undefined) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = val;
      } else {
        el.textContent = val;
      }
    }
  });

  // Href elements with data-i18n-href
  document.querySelectorAll('[data-i18n-href]').forEach(el => {
    el.href = APP_URL;
  });

  // Render stats
  renderStats(t.proof.stats);

  // Render how-it-works steps
  renderSteps(t.howItWorks.steps);

  // Render feature cards
  renderFeatures(t.features.items);

  // Render audience cards
  renderAudience(t.audience.groups);

  // Render FAQ
  renderFAQ(t.faq.items);

  // Render footer links
  renderFooterLinks(t.footer.links);

  // Active lang button
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
  });
}

function setMeta(name, content) {
  if (!content) return;
  // title
  if (name === 'title') { document.title = content; return; }
  // property-based (OG)
  let el = document.querySelector(`meta[property="${name}"]`);
  if (!el) el = document.querySelector(`meta[name="${name}"]`);
  if (el) el.setAttribute('content', content);
}

function getNestedKey(obj, path) {
  return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
}

function renderStats(stats) {
  const container = document.getElementById('stats-grid');
  if (!container) return;
  container.innerHTML = stats.map(s => `
    <div class="stat-card reveal">
      <div class="stat-card__value">${escHtml(s.value)}</div>
      <div class="stat-card__label">${escHtml(s.label)}</div>
    </div>
  `).join('');
  initRevealObserver(container);
}

function renderSteps(steps) {
  const container = document.getElementById('steps-list');
  if (!container) return;
  container.innerHTML = steps.map(s => `
    <div class="step reveal">
      <div class="step__number">${escHtml(s.number)}</div>
      <div class="step__content">
        <div class="step__title">${escHtml(s.title)}</div>
        <p class="step__body">${escHtml(s.body)}</p>
      </div>
    </div>
  `).join('');
  initRevealObserver(container);
}

function renderFeatures(items) {
  const container = document.getElementById('features-grid');
  if (!container) return;
  container.innerHTML = items.map((f, i) => `
    <div class="feature-card reveal reveal-delay-${(i % 3) + 1}">
      <span class="feature-card__icon">${f.icon}</span>
      <div class="feature-card__title">${escHtml(f.title)}</div>
      <p class="feature-card__body">${escHtml(f.body)}</p>
    </div>
  `).join('');
  initRevealObserver(container);
}

function renderAudience(groups) {
  const container = document.getElementById('audience-grid');
  if (!container) return;
  container.innerHTML = groups.map(g => `
    <div class="audience-card reveal">
      <div class="audience-card__icon">${g.icon}</div>
      <div class="audience-card__title">${escHtml(g.title)}</div>
      <p class="audience-card__body">${escHtml(g.body)}</p>
    </div>
  `).join('');
  initRevealObserver(container);
}

function renderFAQ(items) {
  const container = document.getElementById('faq-list');
  if (!container) return;
  container.innerHTML = items.map((item, idx) => `
    <div class="faq-item" data-faq-idx="${idx}">
      <button class="faq-item__trigger" aria-expanded="false" aria-controls="faq-body-${idx}">
        <span>${escHtml(item.q)}</span>
        <span class="faq-item__icon" aria-hidden="true">+</span>
      </button>
      <div class="faq-item__body" id="faq-body-${idx}" role="region" aria-hidden="true">
        <p class="faq-item__answer">${escHtml(item.a)}</p>
      </div>
    </div>
  `).join('');

  // Attach accordion listeners
  container.querySelectorAll('.faq-item__trigger').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const isOpen = item.classList.contains('open');

      // Close all others
      container.querySelectorAll('.faq-item.open').forEach(openItem => {
        openItem.classList.remove('open');
        openItem.querySelector('.faq-item__trigger').setAttribute('aria-expanded', 'false');
        openItem.querySelector('.faq-item__body').setAttribute('aria-hidden', 'true');
      });

      if (!isOpen) {
        item.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
        item.querySelector('.faq-item__body').setAttribute('aria-hidden', 'false');
        trackEvent('faq_open', { question: btn.querySelector('span').textContent });
      }
    });
  });
}

function renderFooterLinks(links) {
  const container = document.getElementById('footer-links');
  if (!container) return;
  container.innerHTML = links.map(l => `
    <a href="${APP_URL}" class="footer__link">${escHtml(l)}</a>
  `).join('');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ============================================================
   LANGUAGE NOTICE BANNER
   ============================================================ */
function initLanguageNotice(activeLang, detectedLang) {
  const notice = document.getElementById('lang-notice');
  if (!notice) return;

  // Show notice if there's a saved lang that differs from detected,
  // or if we detected different from default
  const savedLang = localStorage.getItem(STORAGE_LANG_KEY);

  if (!savedLang && detectedLang !== activeLang) {
    notice.classList.add('visible');
  }

  const changeBtn = document.getElementById('lang-notice-change');
  const dismissBtn = document.getElementById('lang-notice-dismiss');

  if (changeBtn) {
    changeBtn.addEventListener('click', () => {
      notice.classList.remove('visible');
      setLang(detectedLang);
      trackEvent('lang_notice_change', { from: activeLang, to: detectedLang });
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      notice.classList.remove('visible');
      trackEvent('lang_notice_dismiss', { lang: activeLang });
    });
  }
}

/* ============================================================
   LANGUAGE SWITCHER
   ============================================================ */
let currentLang = 'en';

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) return;
  currentLang = lang;
  localStorage.setItem(STORAGE_LANG_KEY, lang);
  renderLang(lang);
  trackEvent('language_switch', { language: lang });
}

function initLangSwitcher() {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const lang = btn.getAttribute('data-lang');
      if (lang === currentLang) return;
      setLang(lang);

      const notice = document.getElementById('lang-notice');
      if (notice) notice.classList.remove('visible');
    });
  });
}

/* ============================================================
   SCROLL REVEAL
   ============================================================ */
function initRevealObserver(root) {
  const targets = (root || document).querySelectorAll('.reveal');
  if (!targets.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  targets.forEach(el => observer.observe(el));
}

/* ============================================================
   CTA ANALYTICS
   ============================================================ */
function initCtaTracking() {
  const eventMap = {
    'cta-hero-primary': 'hero_primary_cta_click',
    'cta-hero-secondary': 'hero_secondary_cta_click',
    'cta-final': 'final_cta_click',
    'cta-sticky': 'sticky_cta_click',
  };

  Object.keys(eventMap).forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('click', () => {
        trackEvent(eventMap[id], { lang: currentLang });
      });
    }
  });

  // Nav CTA
  const navCta = document.getElementById('nav-cta');
  if (navCta) {
    navCta.addEventListener('click', () => {
      trackEvent('nav_cta_click', { lang: currentLang });
    });
  }
}

/* ============================================================
   SECONDARY CTA SMOOTH SCROLL (to how-it-works)
   ============================================================ */
function initHeroSecondaryScroll() {
  const btn = document.getElementById('cta-hero-secondary');
  if (!btn) return;
  btn.addEventListener('click', e => {
    e.preventDefault();
    const target = document.getElementById('how-it-works');
    if (target) {
      const offset = target.getBoundingClientRect().top + window.scrollY - 80;
      window.scrollTo({ top: offset, behavior: 'smooth' });
    }
  });
}

/* ============================================================
   INIT
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  // 1. Theme first (avoids flash)
  initTheme();

  // 2. Language detection
  const detectedLang = resolveLanguage();
  const browserLangRaw = (navigator.language || 'en').split('-')[0].toLowerCase();
  const browserMapped = BROWSER_LANG_MAP[browserLangRaw] || 'en';
  currentLang = detectedLang;

  // 3. Render content
  renderLang(detectedLang);

  // 4. Language switcher
  initLangSwitcher();

  // 5. Language notice (show if user has no saved pref and detected != default 'en')
  initLanguageNotice(detectedLang, browserMapped);

  // 6. Scroll reveal
  initRevealObserver(document);

  // 7. CTA tracking
  initCtaTracking();

  // 8. Secondary CTA scroll
  initHeroSecondaryScroll();
});
