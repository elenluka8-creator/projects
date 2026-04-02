# Unfolda — Branding Summary

Date: 2026-03-15

---

## What we built

### 1. Brand Platform (`Unfolda_Brand_Platform.md`)

- **Mission:** Read any book in any language — with understanding, not just translation.
- **Tone of voice:** Calm · Clear · Literate · Honest
- **Core metaphor:** Unfold = develop the folded meaning
- **Target audience:** educated, motivated readers — language learners, expats, original-text readers

### 2. Visual Identity

**Color palette — "Warm evening with a book":**

| Role | Color | Hex |
|------|-------|-----|
| Primary | Deep navy | #1a1f36 |
| Accent | Warm amber | #e8a849 |
| Background | Cream | #faf6ef |

**Typography:**
- Headings: Satoshi (Medium 500)
- Body: Inter (Regular 400)

**Logo — "Soft open book with text lines":**
- Flat open book, two pages side by side
- Left page (navy) = original text, right page (amber) = translation
- Spine as vertical axis, text lines on both pages
- Rounded corners (rx=5), soft strokes
- Four file variants: light bg, dark bg, cream bg, icon only

---

## Files delivered

```
logo/
├── unfolda-logo-light.svg    — default, for white/light backgrounds
├── unfolda-logo-dark.svg     — for dark navy or black backgrounds
├── unfolda-logo-cream.svg    — for cream (#faf6ef) backgrounds
├── unfolda-icon.svg          — icon only, for favicon/app icon
└── LOGO_USAGE.md             — usage guidelines

Unfolda_Brand_Platform.md     — full brand platform document
```

---

## Recommended next steps

### Immediate (this week)

1. **Finalize logo in Figma** — set the wordmark in Satoshi font, fine-tune kerning and proportions, export PNG/SVG at all needed sizes
2. **Generate logo variants with Logo Diffusion** — use the SVG concept as a reference sketch (Sketch-to-Logo feature) to explore polished AI-generated versions, then pick the best and refine

### Short-term (before launch)

3. **Landing page copywriting** — write hero section, pain/solution block, how-it-works, mode comparison, languages, CTA. All texts aligned with the brand voice.
4. **Landing page build** — recommended: Framer for quick MVP launch, or custom HTML/React as part of the main codebase
5. **Favicon and OG image** — generate from the icon SVG

### Medium-term (post-MVP)

6. **Brand kit expansion** — social media templates, email templates, loading/error state illustrations
7. **Motion design** — subtle "unfolding" animation for the logo and page transitions
8. **App icon** — if native apps are planned, adapt the filled variant (C from the exploration) for iOS/Android guidelines

---

## Tool recommendations

| Task | Tool | Why |
|------|------|-----|
| Logo refinement | Logo Diffusion | Sketch-to-Logo from our SVG, true vector output, 45+ styles |
| Logo polish | Figma | Manual kerning, sizing, export for all formats |
| Landing page (fast) | Framer | AI-assisted, beautiful defaults, live in a day |
| Landing page (custom) | Next.js + Tailwind | Part of the product codebase, full control |
| Illustrations | Midjourney / DALL-E | Hero section imagery, book mockups |
| Copywriting assist | Claude | Landing page texts, A/B headline variants |

---

## Design principles (reference)

From the brand platform — apply these to every design decision:

1. **Calm, not loud** — no aggressive CTAs, no countdown timers, no "limited offer"
2. **Clear, not clever** — if a user can't understand the page in 5 seconds, simplify
3. **Literate, not pretentious** — we can use a beautiful word, but never at the cost of clarity
4. **Book-first** — every visual decision should feel like it belongs in a reading experience
5. **Two colors tell the story** — navy (original) and amber (translation) is the core visual language
