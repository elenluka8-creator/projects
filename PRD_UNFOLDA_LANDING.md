# PRD: High-Conversion Multilingual Landing for Unfolda (Web Service)

## 1. Document Info

- **Product:** Unfolda Landing Page
- **Type:** One-page marketing landing (web)
- **Primary objective:** Increase conversion to start using the Unfolda web service
- **Status:** Draft for product/design/dev alignment
- **Owner:** Product team

---

## 2. Context & Problem

Current language-learning landing experience needs to:

1. Communicate product value in first seconds.
2. Look more visually engaging (modern EdTech/SaaS style).
3. Support geo + browser language logic with manual override.
4. Be fully mobile-first and high-conversion.
5. Position product as a **web service** (not app stores).
6. Keep message clear: currently supported input format is **EPUB only**.

---

## 3. Goals / Non-Goals

### 3.1 Goals

- Build a conversion-oriented landing with clear narrative.
- Provide multilingual UX and content:
  - UI languages: **RU, SR, EN, ES**
- Show language-learning value proposition around parallel paragraphs.
- Support theme toggle (dark/light) with persistence.
- Add measurable analytics events for funnel optimization.
- Ensure responsive quality for mobile and desktop.

### 3.2 Non-Goals

- No backend feature development in this scope.
- No account system or onboarding flow implementation.
- No app-store distribution messaging (web-only positioning).

---

## 4. Target Audience

- Expats and relocators learning new language environments.
- Students and professionals reading domain literature in original languages.
- Book lovers wanting original-language reading with context-based comprehension.

---

## 5. Value Proposition (Hero)

### 5.1 Core message

- Read favorite books in original languages.
- Understand words via contextual parallel paragraphs.
- Learn naturally without constant translator switching.

### 5.2 Key constraints in copy

- Mention **EPUB** support (current format).
- Mention available learning language combinations:
  - English, Spanish, Serbian, Russian.

---

## 6. Functional Requirements

## 6.1 Page Structure (single page)

1. Hero
2. Social proof / proof metrics
3. Problem & solution
4. How it works
5. Features
6. Audience
7. FAQ
8. Final CTA section

## 6.2 Language System

- Supported interface languages:
  - `ru`, `sr`, `en`, `es`
- Manual switcher in top bar: RU / SR / EN / ES.
- Auto language detection order:
  1. Persisted user choice (localStorage)
  2. Geo mapping:
     - RU -> ru
     - RS, ME, BA, HR, SI -> sr
  3. Browser language fallback (`navigator.language`)
     - ru -> ru
     - sr/hr/bs/sl -> sr
     - es -> es
     - default -> en

## 6.3 Theme System

- Theme modes: dark / light.
- Toggle in top bar.
- Persist selected theme in localStorage.

## 6.4 CTA / Navigation

- CTA destination must be **web-service URL**:
  - `https://unfolda.ai`
- Remove app-store semantics in copy.
- Keep sticky mobile CTA for small screens.

## 6.5 Mascot Block

- Hero should include mascot visual + localized mascot label.
- Required localized mascot titles:
  - **EN:** `Uno the Owl — Your reading companion.`
  - **ES:** `El búho Uno — Tu guía de lectura.`
  - **SR:** `Sova Uno — Tvoj saputnik u čitanju.`
  - **RU:** `Филин Уно — Ваш помощник в чтении.`

---

## 7. UX/UI Requirements

## 7.1 Visual Direction

- Style: modern EdTech/SaaS with strong visual identity.
- Desired tone: clean + premium + engaging.
- Keep “air” (breathing space), readable hierarchy.
- Add visual elements (mascot, device-style preview, accents) without clutter.

## 7.2 Readability Requirements

- Fix low-contrast issues in light theme:
  - Secondary buttons
  - Cards
  - Supporting text
  - Chips/notices
- Hero title should not visually “hang” or overwhelm viewport.

## 7.3 Responsive Requirements

- Mobile-first layout.
- Validate key widths: 320, 360, 375, 390, 414, 768.
- No overlapping controls in top bar.
- Sticky mobile CTA must not hide core content.

---

## 8. Content Requirements

## 8.1 Product Scope in copy

- Explicitly state support for **EPUB**.
- Do not claim FB2/PDF if not supported.
- Do not over-focus on one country; keep global positioning.

## 8.2 Localized consistency

- All major sections must be translated consistently in RU/SR/EN/ES.
- Include localized CTA labels, FAQ, proof blocks, trust statements.

---

## 9. Analytics & Tracking Requirements

- Keep GA4 + Yandex Metrika integration points.
- Track events at minimum:
  - Hero primary CTA click
  - Hero secondary CTA click
  - Final web CTA click
  - Sticky CTA click
  - Language switch
  - Theme switch
  - FAQ open
  - Language notice actions (change/dismiss)

---

## 10. SEO & Sharing Requirements

- Meta title/description localized by active language.
- OG/Twitter title/description localized by active language.
- Keep index/follow robots directives.

---

## 11. Technical Requirements

- Static front-end files:
  - `index.html`
  - `styles.css`
  - `app.js`
  - `locales.js`
- Add cache-busting strategy for static assets (query versioning).
- No dependency on backend build system required for page rendering.

---

## 12. Acceptance Criteria (DoD)

Landing is considered accepted when:

1. UI language switcher includes RU/SR/EN/ES and works end-to-end.
2. Auto language detection follows specified priority and mapping.
3. Mascot titles exactly match required strings in all 4 languages.
4. Light theme readability issues are resolved (secondary CTA + body text + cards).
5. Hero no longer appears visually cramped/overwhelming.
6. CTA messaging is web-service oriented and points to `https://unfolda.ai`.
7. EPUB-only messaging is consistent across hero/how/FAQ/proof.
8. Mobile responsive behavior passes checks for common viewport widths.
9. Analytics events fire for core interactions.
10. SEO/OG metadata updates by active language.

---

## 13. Risks & Mitigations

## 13.1 Risk: stale local cache shows old visuals

- **Mitigation:** versioned asset query params + hard refresh guidance.

## 13.2 Risk: mismatched copies across languages

- **Mitigation:** centralized locale dictionary and i18n key audit.

## 13.3 Risk: visual complexity harms readability

- **Mitigation:** enforce contrast checks and typography limits on hero.

---

## 14. Open Questions for Product/Design

1. Should Spanish be geo-prioritized for specific countries, or browser-only fallback remains enough?
2. Is mascot style final, or should design team provide brand-approved illustration pack?
3. Should hero line breaks be hard-controlled per language for pixel-perfect typography?
4. Do we need an A/B test plan for hero messaging variants before production rollout?

---

## 15. Suggested Next Iteration (post-PRD)

- Visual polish pass for hero composition (desktop + mobile).
- Formal QA checklist with screenshots per language and theme.
- A/B testing of hero headline + CTA text.
- Public deployment checklist (Netlify/Vercel/Nginx) with cache headers.

