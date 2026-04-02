# COST-3 — Express Tier Visibility

**Feature ID:** COST-3  
**Status:** spec  
**Author:** Product  
**Date:** 2026-03-28  

---

## Feature Summary

The upload form already exposes three quality tiers (Express, Standard, Premium), but Standard is the default and its descriptions give users no signal about the magnitude of the cost difference. Express (Claude Haiku) is ~5× cheaper than Standard and produces quality that is adequate for most casual reading; users who are unaware of this pay significantly more than necessary. This feature makes Express the pre-selected tier and improves all tier descriptions so users understand what they are choosing before looking at the credit estimate.

---

## User Problem

Most users who want a translated book for personal reading are well-served by Express quality. However:

- Standard is the pre-selected default, so users never notice Express unless they actively explore the selector.
- The current Express description ("Fast and affordable") conveys no magnitude — "affordable" relative to what?
- The current Standard description labels itself "recommended", anchoring the user toward a tier that costs 3–6× more per book.
- Users only see the credit cost difference after they switch tiers and wait for a re-estimate. There is no signal at the point of selection.

Result: Express is underutilised, users spend more credits than needed, and credits run out sooner — reducing retention.

---

## Goal

Make Express the obvious starting point for most users, with tier descriptions that communicate cost and quality trade-offs clearly enough that users can make an informed choice without needing to try both tiers.

---

## Feature Fit

Unfolda is a credit-based service. Reducing unnecessary credit consumption extends the useful lifetime of a user's initial grant, improves first-session value, and reduces the likelihood that users exhaust credits before experiencing the product's value. Making Express the default is also operationally beneficial — it reduces LLM cost per job.

---

## PRD / Architecture Alignment

The PRD defines credit-based usage limits and states that estimated credit cost is shown before job confirmation. This feature does not change the credit system, pricing model, or any backend behaviour — it only changes what the UI pre-selects and how tier options are described. No conflicts with existing decisions in `docs/DECISIONS.md`.

---

## In Scope

- Change the default quality tier from `standard` to `express` in `web/app/[locale]/upload/page.tsx`
- Update tier descriptions in i18n message files to communicate relative cost and quality (en, ru, es, sr — the four locale files that currently exist)
- Add a visible "Recommended" badge or label to the Express tier card; remove the "recommended" label from Standard's description
- The `ModeCard` component may be extended to accept an optional badge prop, or a badge may be rendered inline in the tier fieldset

---

## Out of Scope

- No new backend endpoints or API changes
- No monetary price display ($ amounts) — credits only
- No new tier or model
- No changes to the credit estimation logic
- No i18n for the 10 locale files that do not yet exist (those would be added when TASK-24 ships)
- No changes to the jobs list or job detail pages
- No A/B testing or feature flags

---

## Acceptance Criteria

1. When the upload form reaches the `done` phase (after precheck), the Express tier is pre-selected by default.
2. The Express tier card description conveys the relative cost advantage in a user-understandable way (e.g. "~5× fewer credits · good quality for most books").
3. The Express tier card carries a visible "Recommended" badge or equivalent label.
4. The Standard tier card description no longer contains the word "recommended".
5. The Premium tier card description conveys that it is for highest-quality needs.
6. All four existing locale message files (`en.json`, `ru.json`, `es.json`, `sr.json`) are updated with new tier descriptions; no locale file is left with the old "recommended" wording for Standard.
7. Switching tier selection continues to trigger a credit re-estimate (existing behaviour is preserved, no regression).
8. `npm run build` compiles without errors after the change.
9. No backend files are modified.

---

## Open Questions

- None. The approach is well-defined and the scope is narrow.

---

## Risks / Dependencies

| Risk | Likelihood | Mitigation |
|---|---|---|
| Changing the default tier from Standard to Express surprises existing users who have already formed expectations | Low (feature is early; user base is small) | Descriptions explain the trade-off; user can still select Standard freely |
| "~5×" framing is approximate and may not match every book | Low | Use qualifying language ("up to", "typically") in the description copy |
| ru/es/sr translations of new descriptions require accurate copy | Medium | Provide English source; translate using the same approach as other upload keys; verify strings in context |
| ModeCard badge renders poorly on narrow viewports (mobile-first) | Low | Badge is a small inline pill; test at 375px width before shipping |

---

## Optional Follow-ups

- Once TASK-24 (full i18n) ships, extend new tier descriptions to all 14 locales.
- If analytics show Express adoption still low after this change, consider surfacing the estimated credit saving as a delta alongside each tier card (requires no backend change — the estimate is already fetched per tier).

---

## Proposed MVP Slice

Change the default tier to Express, improve all three tier descriptions, and add a visual "Recommended" badge to Express. Split across two tasks to keep each independently reviewable: one for the i18n content change plus the default, and one for the visual badge in the component.

---

## Task Breakdown

### COST-3-T1 — Change default tier to Express and update tier descriptions [MVP]

- **complexity:** small
- **goal:** Make Express the pre-selected tier and replace all three tier descriptions with copy that communicates cost and quality trade-offs.
- **scope:**
  - `web/app/[locale]/upload/page.tsx` — change `useState<...>("standard")` to `useState<...>("express")`
  - `web/messages/en.json` — update `tierExpressDesc`, `tierStandardDesc`, `tierPremiumDesc`; remove "recommended" from Standard; add "recommended" context to Express description
  - `web/messages/ru.json`, `web/messages/es.json`, `web/messages/sr.json` — same key updates, translated appropriately
- **dependencies:** none
- **acceptance criteria:**
  - Express is pre-selected when the form loads
  - `tierExpressDesc` communicates the ~5× credit advantage and suitability for most books
  - `tierStandardDesc` no longer contains "recommended"
  - All four locale files updated; no old "recommended" wording remains for Standard in any locale
  - `npm run build` exits 0

---

### COST-3-T2 — Add "Recommended" badge to Express tier card [MVP]

- **complexity:** small
- **goal:** Give the Express tier a visible recommended badge so users have a clear visual signal at the point of selection, without relying on reading the description text alone.
- **scope:**
  - `web/app/[locale]/upload/page.tsx` — extend the tier fieldset or `ModeCard` to render a small badge (e.g. "Recommended") on the Express card only. The badge must not break the existing card layout on narrow viewports (375px minimum).
  - `web/messages/en.json` (and ru, es, sr) — add a `tierRecommendedBadge` key (e.g. "Recommended") if the badge label is sourced from i18n; alternatively the badge may use a hardcoded English label given the badge is a single word and i18n for it can be deferred to TASK-24.
- **dependencies:** COST-3-T1 (descriptions updated; base state understood)
- **acceptance criteria:**
  - Express card displays a small badge label distinct from the title and description text
  - Standard and Premium cards display no badge
  - Badge is visible at 375px viewport width without overflow or layout breakage
  - `npm run build` exits 0

---

## Recommended Next Task

**COST-3-T1** — it is the smallest, fully self-contained change (default + copy), produces immediate visible impact, and unblocks COST-3-T2.

---

## docs/TASKS.md Update

Update COST-3 entry: replace "TBD by Product agent" acceptance criteria with the criteria defined in this spec (see Acceptance Criteria section above). Keep status as `planned`.

---

## Assumptions Made

- The four existing locale files (en, ru, es, sr) are the only ones that require updating now; the remaining 10 locales will be handled when TASK-24 ships.
- A hardcoded English "Recommended" badge label is acceptable for COST-3-T2 since single-word badge i18n can be deferred to TASK-24 without user harm.
- The credit re-estimate triggered on tier change (existing behaviour) is sufficient to show users the quantitative difference after they switch; no additional inline cost comparison is required for this task.
