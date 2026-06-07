# Shared design layer

One visual identity for all three surfaces:

1. **Collected Works React app** — Library + search + reading (`frontend/`)
2. **Savitri Study static site** — `savitri-wiki/`
3. The Library prototype these were extracted from (`docs/prototype/`)

## What's here

| File | Purpose |
|------|---------|
| `tokens.css` | CSS custom properties — colours, fonts, shadows, radius/spacing/motion scales. **The single source of truth.** |
| `fonts.css`  | `@import` for the Google Fonts type stack. Convenience for the static site. |

Why CSS custom properties and not a React component package: the Savitri
site is plain HTML, so the only thing all three surfaces can genuinely share
is CSS variables. Change a value here, every surface updates.

## How each surface consumes it

### React app (`frontend/`)
Put the fonts in `index.html` `<head>` (faster than `@import`):

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&family=Spectral:ital,wght@0,300;0,400;0,500;0,600;1,400&family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

Then import the tokens once at the app entry (e.g. `src/index.css` or
`main.jsx`):

```css
@import '../../design/tokens.css';
```

(Exact path set during the Vite migration; Vite resolves it at build time.)

### Static site (`savitri-wiki/`)
Add two `<link>`s to each page `<head>`:

```html
<link rel="stylesheet" href="/design/fonts.css" />
<link rel="stylesheet" href="/design/tokens.css" />
```

Then reference variables in the page CSS, e.g. `color: var(--ink);
font-family: var(--serif);`.

## Rules

- Never hardcode a colour/font that exists as a token — use `var(--…)`.
- Add a new shared value here, not in a surface's local CSS.
- The `:root` block in `tokens.css` mirrors the prototype value-for-value,
  so the prototype CSS keeps working unchanged when merged into the app.
