# Reno-Budget — Claude rules

Short, enforceable rules. Full system: `docs/design-system.md`.

## Frontend — design tokens (light mode only)

- **Never** use raw `slate-*`, `red-*`, `emerald-*`, `amber-*`, `blue-*`,
  `green-*`, `yellow-*` Tailwind colours. Use semantic tokens:
  - Surfaces: `bg-paper`, `bg-paper-sunk`, `bg-paper-raised`.
  - Text: `text-ink` (body), `text-ink-muted` (secondary), `text-ink-subtle`
    (labels/hints — **AA Large only, never body**).
  - Borders: `border-rule` (hairline).
  - Accent: `text-accent`, `bg-accent-soft` (single ochre, used sparingly).
  - Semantic: `text-positive` / `text-negative` / `text-warning` (+ `*-soft`
    backgrounds) — **only when the data means good/bad/attention**, never as a
    style choice.
- **Never** use `bg-white`, `text-white`, `text-black`. Use `bg-paper-raised`,
  `text-paper`, `text-ink`.
- **Money values** render as `font-mono tabular-nums text-right`. Principal
  amounts in `text-ink`; only variance/diff figures may be semantic-coloured.
- **Headings** use `font-display` (Fraunces — already the default on `h1–h4`).
  Body/UI default to `font-sans` (Inter Tight). Code, codes (BKP) and numbers
  use `font-mono` (JetBrains Mono).
- **Sections** are separated by hairline rules (`border-y border-rule`), not by
  nested cards or stacked drop-shadows. Use `shadow-panel` only on true overlays
  (dialogs, popovers).
- **Buttons:** primary = `bg-ink text-paper hover:bg-ink/85`. Secondary =
  `border border-rule text-ink-muted hover:border-ink/30 hover:text-ink`.
- **Inputs:** idle = `border border-rule bg-paper-raised`; focus =
  `focus:border-accent focus:outline-none` (the global focus ring is inherited).
- **Light mode only.** Do **not** introduce `dark:` variants without an explicit
  user request.
- **Self-hosted fonts** via `@fontsource-variable/*`. Do not pull from the
  Google Fonts CDN.

Grep guard before declaring a frontend change done:

```bash
grep -rnE 'slate-[0-9]|emerald-[0-9]|red-[0-9]|amber-[0-9]|yellow-[0-9]|blue-[0-9]|green-[0-9]|\btext-white\b|\btext-black\b|\bbg-white\b' frontend/src --include='*.ts' --include='*.tsx'
```

Output must be empty. If it isn't, fix before commit.

## Where the rest lives

- Design system: `docs/design-system.md`
- Architecture decisions: `docs/architecture/`
- How-tos: `docs/howto/`
