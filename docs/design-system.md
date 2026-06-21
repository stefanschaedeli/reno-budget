# Reno-Budget Design System

> **Audience:** anyone (human or AI) about to touch a `.tsx` file. Read the
> "Aesthetic intent" and "Anti-patterns" sections at minimum before you write
> a new component — these are the rules most likely to be violated reflexively.

---

## 1. Aesthetic intent — "Architect's notebook"

Reno-Budget is a Swiss family renovation budget tracker, used over months and
years, mostly to read numbers and trust them. The UI is **calm, editorial,
disciplined** — Swiss publishing meets blueprint paper.

Concrete consequences:

- **Warm paper, not white-blue SaaS.** Page background is `--paper` (`#FBF9F4`),
  a low-glare off-white. Never `bg-white` (the token is `bg-paper-raised` for
  the rare elevated surfaces).
- **Ink, not slate.** Body text is `--ink` (`#0E1A2B`), a deep navy. Slate is
  banned (see anti-patterns).
- **Hairlines, not cards-in-cards.** Sections are separated by 1px `--rule`
  borders, not stacked drop-shadows. Use `border-rule` and `border-y border-rule`
  patterns; reserve `shadow-panel` for true overlays (dialogs, popovers).
- **Numbers are sacred.** All CHF amounts and BKP codes render in
  `font-mono tabular-nums text-right`. Money is the content; treat it that way.
- **One accent.** Ochre `--accent` is the only chromatic accent. Use sparingly:
  active nav marker, focus ring, link-hover. No purple, no blue, no teal.
- **Semantic colour, not decoration.** `--positive` (moss), `--negative` (clay),
  `--warning` (amber) appear only on data that *means* good/bad/attention —
  variance, overdue, due-soon. Never as a style choice.
- **Light mode only.** Decided. See § 6.

---

## 2. Token table

All colours are CSS variables declared in `frontend/src/index.css` `:root` and
re-exposed through `frontend/tailwind.config.js` as Tailwind utilities. Use the
utilities (`bg-paper`, `text-ink`, etc.) in components — **never the raw hex
values, never raw `slate-*`/`red-*`/`emerald-*`**.

| Token utility       | Hex       | Use                                                 | Contrast on `--paper` |
| ------------------- | --------- | --------------------------------------------------- | --------------------- |
| `bg-paper`          | `#FBF9F4` | page background                                     | —                     |
| `bg-paper-sunk`     | `#F4F0E6` | inset / table zebra / input idle                    | —                     |
| `bg-paper-raised`   | `#FFFFFF` | elevated panels, dialogs                            | —                     |
| `text-ink`          | `#0E1A2B` | primary text, headings, primary buttons             | **15.8 : 1**          |
| `text-ink-muted`    | `#4A5468` | secondary text, labels, helper copy                 | **7.4 : 1**           |
| `text-ink-subtle`   | `#7A8294` | placeholders, count badges (**AA Large only**)      | **3.7 : 1**           |
| `border-rule`       | `#E5DFD0` | hairline borders, dividers                          | —                     |
| `text-accent`       | `#B5651D` | links on hover, active nav marker, focus ring       | **5.1 : 1**           |
| `bg-accent-soft`    | `#F3E7D6` | subtle accent backgrounds (selections)              | —                     |
| `text-positive`     | `#2F5D3A` | under-budget, paid                                  | **6.6 : 1**           |
| `bg-positive-soft`  | `#E1ECDF` | positive banner backgrounds                         | —                     |
| `text-negative`     | `#9A2A2A` | over-budget, overdue, errors                        | **6.2 : 1**           |
| `bg-negative-soft`  | `#F1DAD8` | negative banner backgrounds                         | —                     |
| `text-warning`      | `#C58B2A` | due-soon, pending review                            | **3.5 : 1** (Large)   |
| `bg-warning-soft`   | `#F6E8CF` | warning banner backgrounds                          | —                     |

`text-ink-subtle` and `text-warning` are **AA-Large only** (≥18 pt or ≥14 pt
bold). Do not use them for body copy — that is exactly the contrast bug we just
fixed.

---

## 3. Typography

| Role             | Family                | Tailwind         | Notes                                                |
| ---------------- | --------------------- | ---------------- | ---------------------------------------------------- |
| Display, headings | **Fraunces Variable** | `font-display`   | Soft modern serif; warm. Set on `h1–h4` by default in `index.css`. |
| Body, UI         | **Inter Tight Variable** | `font-sans`   | Body default. Tracked at `-0.01em` (set on `body`).  |
| Numbers, code    | **JetBrains Mono Variable** | `font-mono` | All CHF amounts, BKP codes, year fields.             |

All fonts are **self-hosted via `@fontsource-variable`** packages — never the
Google Fonts CDN (we're self-hosted on TrueNAS; no third-party requests at
runtime).

The body letter-spacing of `-0.01em` is what makes Inter Tight read editorial
instead of SaaS. Don't override it on body copy.

---

## 4. Money rendering (single rule)

```tsx
<span className="font-mono tabular-nums text-right">{formatChf(amount)}</span>
```

- `font-mono` for the family.
- `tabular-nums` so columns of CHF align vertically.
- `text-right` because money has a decimal point readers anchor on.
- **Semantic colour only on variance.** A principal amount is always `text-ink`.
  Add `text-positive` / `text-negative` *only* to a diff/variance figure, never
  to the planned or actual amount itself.

---

## 5. Patterns and anti-patterns

### Patterns

- **Section divider:** `border-y border-rule` around a `<section>` instead of a
  card with shadow. See `BudgetCard.tsx`.
- **Active nav marker:** absolute-positioned 3px-wide ochre bar on the left edge
  of the active `NavLink`. See `AppLayout.tsx::SidebarLink`.
- **Status dot, not pill:** `1.5×1.5` rounded-full coloured dot in front of a
  label, instead of a tinted pill. See `CostItemBoard.tsx`.
- **Field label:** `text-[0.65rem] font-semibold uppercase tracking-[0.18em]
  text-ink-subtle`. Reused in `BudgetCard`, `CostItemFilters`.
- **Input idle / focused:** `border border-rule bg-paper-raised` idle,
  `focus:border-accent focus:outline-none` focused. Focus ring inherited from
  global `:focus-visible` rule in `index.css`.
- **Primary button:** `bg-ink text-paper hover:bg-ink/85`.
- **Secondary / cancel button:** `border border-rule text-ink-muted
  hover:border-ink/30 hover:text-ink`.

### Anti-patterns — STOP if you're about to do this

- ❌ Raw `slate-*`, `red-*`, `emerald-*`, `amber-*`, `blue-*`, `green-*`,
  `yellow-*` Tailwind colour utilities. Use tokens instead. The CI grep guard
  is `grep -rnE 'slate-[0-9]|emerald-[0-9]|red-[0-9]|...' frontend/src` and it
  should return zero.
- ❌ `bg-white` / `text-white` / `text-black`. Use `bg-paper-raised`, `text-paper`,
  `text-ink`.
- ❌ `text-ink-subtle` on body copy. AA-Large only — labels, hints, count badges.
- ❌ Cards inside cards (nested `rounded-lg border bg-paper-raised` blocks). Use
  hairlines (`border-y border-rule`) to separate sections.
- ❌ Multi-layer drop shadows for hierarchy. Use `shadow-panel` only on overlays
  (dialogs, popovers); everything else gets a border.
- ❌ Decorative colour. If you reach for green/red/amber, the data must *mean*
  good/bad/attention. Otherwise stay in ink + paper.
- ❌ Introducing a new colour ad-hoc. Add a token to `index.css` and
  `tailwind.config.js` first; update this doc's token table in the same change.
- ❌ Drop-shadow stacks (`shadow-md`, `shadow-lg`, `shadow-xl`). Use the named
  `shadow-panel` only.
- ❌ Pulling fonts from Google Fonts CDN. Use `@fontsource-variable` packages.
- ❌ Adding `dark:` variants. See § 6 — light only by decision.

---

## 6. Decision log

Recording *why* so the next refactor doesn't undo these silently.

- **Light mode only.** Tracking budgets for years; consistency matters more than
  preference. Picking one mode and executing it excellently beats half-built
  dark-mode coverage. Revisit only after explicit user request.
- **Self-hosted fonts via `@fontsource-variable`.** Consistent with the project's
  self-hosted-on-TrueNAS ethos. No runtime calls to fonts.googleapis.com.
- **Fraunces + Inter Tight + JetBrains Mono.** Fraunces gives the editorial /
  Swiss-publishing warmth without being a Helvetica cliché; Inter Tight is the
  workhorse, tightened with `-0.01em` so it doesn't read as generic SaaS;
  JetBrains Mono has well-shaped tabular figures for CHF alignment, which is
  the whole game here.
- **Architect's-notebook aesthetic over generic dashboard.** The original UI
  used stock Tailwind `slate-*` with no theme — readable but characterless, and
  with marginal `text-slate-700`-on-`bg-slate-100` contrast that the user
  reported as unreadable. The rework solves the contrast problem *and* gives the
  app an identity that matches its domain (construction, blueprints, eBKP-H).
- **Semantic colour is structural, not stylistic.** Decisions about
  positive/negative/warning live in the data, not in the designer's palette
  whim. Makes future variance/state UI trivially consistent.

---

## 7. Adding a new component — checklist

Before opening a PR with a new component or page:

1. Uses only token utilities (`bg-paper*`, `text-ink*`, `border-rule`,
   `text-accent`, `text-positive`, `text-negative`, `text-warning`). No raw
   colour stops.
2. Headings use `font-display` (set automatically on `h1–h4`); body uses default
   `font-sans`; money/codes use `font-mono tabular-nums`.
3. Money values include `text-right` and are `text-ink` (variance figures may
   add `text-positive` / `text-negative`).
4. Hairlines (`border-rule`) preferred over cards-on-cards.
5. Form inputs use `border border-rule bg-paper-raised focus:border-accent
   focus:outline-none`.
6. No `dark:` variants.
7. `npm run build` is clean.
8. `grep -rnE 'slate-[0-9]|emerald-[0-9]|red-[0-9]|amber-[0-9]|yellow-[0-9]|blue-[0-9]|green-[0-9]' frontend/src` returns nothing new.
