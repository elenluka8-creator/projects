# COST-3 — Express Tier Visibility: Implementation Plan

**Plan ID:** ARCH-COST-3  
**Task IDs:** COST-3-T1, COST-3-T2  
**Date:** 2026-03-28  
**Architect:** Architect agent  

---

## Task Restatement

Implement COST-3 in two small tasks: (T1) change the quality tier default from `standard` to `express` and update all three tier descriptions in all four locale files; (T2) add a "Recommended" badge to the Express tier card in the upload form.

---

## Plan

### COST-3-T1 — Change default tier + update descriptions [small]

1. **Change the `qualityTier` default** in `web/app/[locale]/upload/page.tsx`, line 415:
   - Current: `useState<"express" | "standard" | "premium">("standard")`
   - Change to: `useState<"express" | "standard" | "premium">("express")`
   - No other code logic is affected; `qualityTier` flows directly into `fetchEstimate` and `api.submitJob` unchanged.

2. **Update `tierExpressDesc`** in all four locale files — remove "affordable" vagueness, add relative cost signal and suitability statement.

3. **Update `tierStandardDesc`** in all four locale files — remove "recommended" word entirely, retain quality signal.

4. **Update `tierPremiumDesc`** in all four locale files — retain highest-quality signal, make it clearer this is for demanding needs.

### COST-3-T2 — Add "Recommended" badge to Express tier card [small]

5. **Extend `ModeCard`** to accept an optional `badge?: string` prop. Render the badge as a small inline pill immediately after the label text when `badge` is provided.

6. **Pass `badge="Recommended"` for the Express entry** in the `QUALITY_TIERS.map()` rendering block. Standard and Premium receive no badge prop.

---

## Acceptance Criteria

- Express is pre-selected when the upload form reaches the `done` phase.
- `tierExpressDesc` communicates the ~5× credit advantage and suitability for most books in all four locales.
- `tierStandardDesc` contains no form of "recommended" in any locale.
- `tierPremiumDesc` conveys highest-quality, higher-cost positioning in all four locales.
- Express tier card renders a visible "Recommended" badge; Standard and Premium do not.
- Badge does not break card layout at 375px viewport width.
- Switching tier still triggers a credit re-estimate (no regression to existing `useEffect` dependency array on `qualityTier`).
- `npm run build` exits 0.
- No backend files are modified.

---

## Non-goals

- No backend changes.
- No new npm packages.
- No `docs/DECISIONS.md` entry (no new external dependency introduced).
- No `docs/ARCHITECTURE.md` update (pure UI change, no pipeline or module boundary change).
- No i18n for the badge text in this task (deferred to TASK-24; hardcoded English "Recommended" is acceptable).
- No i18n updates beyond the four existing locale files (remaining 10 locales deferred to TASK-24).
- No inline credit delta comparison between tiers.
- No A/B testing or feature flags.

---

## Dependencies

- **external:** none
- **internal:** `ModeCard` component (extended in-place in `page.tsx`); no separate component file

---

## Files

- **modify:** `web/app/[locale]/upload/page.tsx` — change default state value; extend `ModeCard` props; pass badge to Express card
- **modify:** `web/messages/en.json` — update `tierExpressDesc`, `tierStandardDesc`, `tierPremiumDesc`
- **modify:** `web/messages/ru.json` — same three keys, Russian translations
- **modify:** `web/messages/es.json` — same three keys, Spanish translations
- **modify:** `web/messages/sr.json` — same three keys, Serbian translations
- **read-only (referenced):** `docs/features/COST-3-express-tier-visibility.md`
- **read-only (referenced):** `docs/features/COST-3-analytics.md`

---

## Risks

- **"~5×" copy is approximate** — the real ratio varies by book length and language pair. Mitigation: use qualifying language such as "typically up to 5×" or "~5× fewer" to signal approximation without implying a guarantee.
- **Badge pill overflow on narrow viewports** — the Express card header row will contain label text + badge. Mitigation: use `flex-wrap` or keep the badge compact (≤ 12 chars). Test at 375px.
- **ru/es/sr copy accuracy** — translations are provided below by the Architect; Builder should verify strings display correctly in context before submitting for review.

---

## Architectural Notes

- `ModeCard` is a pure presentational component defined locally in `page.tsx`. Extending it with an optional `badge` prop is safe: the prop defaults to `undefined` and existing call sites (translation mode cards) pass nothing, so no regression is possible.
- The quality tier change from `"standard"` to `"express"` as the initial `useState` value is safe: the value flows into `fetchEstimate` via the `useEffect` dependency array (line 497), so the initial estimate on page load will already use Express. No other component reads `qualityTier` directly.
- No new i18n key for the badge is required for this task. The badge text is hardcoded as the English string `"Recommended"` in JSX, consistent with the spec's deferral note.

---

## Precise Change Specifications

### T1-A: Default change (`page.tsx` line 415)

```
- const [qualityTier, setQualityTier] = useState<"express" | "standard" | "premium">("standard");
+ const [qualityTier, setQualityTier] = useState<"express" | "standard" | "premium">("express");
```

### T1-B: i18n message updates (all four locales)

#### en.json
| Key | Current value | New value |
|---|---|---|
| `tierExpressDesc` | `"Fast and affordable"` | `"Typically ~5× fewer credits · good quality for most books"` |
| `tierStandardDesc` | `"Optimal quality · recommended"` | `"Higher-quality translation · uses more credits"` |
| `tierPremiumDesc` | `"Highest quality, slower and more expensive"` | `"Best possible quality · most credits · slower"` |

#### ru.json
| Key | Current value | New value |
|---|---|---|
| `tierExpressDesc` | `"Быстро и дёшево"` | `"Обычно ~в 5 раз меньше кредитов · хорошее качество для большинства книг"` |
| `tierStandardDesc` | `"Оптимальное качество · рекомендуется"` | `"Более высокое качество перевода · расходует больше кредитов"` |
| `tierPremiumDesc` | `"Наивысшее качество, медленнее и дороже"` | `"Наилучшее качество · больше всего кредитов · медленнее"` |

#### es.json
| Key | Current value | New value |
|---|---|---|
| `tierExpressDesc` | `"Rápido y económico"` | `"Normalmente ~5× menos créditos · buena calidad para la mayoría de libros"` |
| `tierStandardDesc` | `"Calidad óptima · recomendado"` | `"Traducción de mayor calidad · consume más créditos"` |
| `tierPremiumDesc` | `"Máxima calidad, más lento y costoso"` | `"La mejor calidad posible · más créditos · más lento"` |

#### sr.json
| Key | Current value | New value |
|---|---|---|
| `tierExpressDesc` | `"Brzo i povoljno"` | `"Obično ~5× manje kredita · dobra kvaliteta za većinu knjiga"` |
| `tierStandardDesc` | `"Optimalni kvalitet · preporučeno"` | `"Kvalitetniji prevod · troši više kredita"` |
| `tierPremiumDesc` | `"Najviši kvalitet, sporije i skuplje"` | `"Najbolji mogući kvalitet · najviše kredita · sporije"` |

### T2-A: Extend `ModeCard` component signature (`page.tsx` lines 249–292)

Add `badge?: string` to the props interface:

```tsx
function ModeCard({
  label,
  description,
  selected,
  onSelect,
  badge,
}: {
  label: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  badge?: string;
}) {
```

Render the badge inline, immediately after the label `<p>` element inside the inner `<div>`:

```tsx
<div>
  <div className="flex items-center gap-2">
    <p className="text-sm font-medium" style={{ color: "var(--color-navy)" }}>{label}</p>
    {badge && (
      <span
        className="rounded-full px-2 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "var(--color-amber)", color: "var(--color-navy)" }}
      >
        {badge}
      </span>
    )}
  </div>
  <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--color-navy)", opacity: 0.6 }}>
    {description}
  </p>
</div>
```

### T2-B: Pass badge to Express tier card (`page.tsx` lines 629–639)

Change the `QUALITY_TIERS.map()` render block to pass `badge` only for Express:

```tsx
{QUALITY_TIERS.map((tier) => (
  <ModeCard
    key={tier.value}
    label={tier.label}
    description={tier.description}
    selected={qualityTier === tier.value}
    onSelect={() => setQualityTier(tier.value)}
    badge={tier.value === "express" ? "Recommended" : undefined}
  />
))}
```

---

## Assumptions Made

- `var(--color-amber)` is an available CSS custom property in the existing design system (it is referenced elsewhere in `page.tsx` at lines 121 and 179); using it for the badge background is consistent with the existing amber accent usage and requires no new token.
- A hardcoded English badge label `"Recommended"` is acceptable for COST-3 given the spec explicitly notes i18n deferral to TASK-24.
- The `flex items-center gap-2` wrapper for label + badge is safe at 375px because the badge text ("Recommended", 11 characters) renders as a small pill and the label text wraps naturally.

---

## Smallest Next Step

Builder should implement T1 first (the one-line default change + five JSON key updates) as a standalone commit, verify `npm run build` passes, then implement T2 (ModeCard badge extension) as a second commit.

---

## Optional Follow-ups

- Once TASK-24 (full i18n) ships, replace the hardcoded `"Recommended"` badge string with a `t("tierRecommendedBadge")` key across all 14 locales.
- If post-launch analytics show Express adoption is still low, consider rendering the credit delta (`estimate_standard - estimate_express`) inline next to each tier card to make the saving concrete without requiring a tier switch.
