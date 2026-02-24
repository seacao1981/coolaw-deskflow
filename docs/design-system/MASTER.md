# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Coolaw DeskFlow
**Generated:** 2026-02-21
**Category:** AI Agent Desktop Application / Developer Tool
**Style:** Dark Mode Dashboard + Minimal IDE Aesthetic

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable | Tailwind |
|------|-----|--------------|----------|
| Background (Deep) | `#0B0F1A` | `--color-bg-deep` | `bg-slate-950` |
| Background (Base) | `#0F172A` | `--color-bg-base` | `bg-slate-900` |
| Surface (Card) | `#1E293B` | `--color-surface` | `bg-slate-800` |
| Surface (Elevated) | `#334155` | `--color-surface-elevated` | `bg-slate-700` |
| Border (Default) | `#334155` | `--color-border` | `border-slate-700` |
| Border (Subtle) | `#1E293B` | `--color-border-subtle` | `border-slate-800` |
| Text (Primary) | `#F8FAFC` | `--color-text-primary` | `text-slate-50` |
| Text (Secondary) | `#94A3B8` | `--color-text-secondary` | `text-slate-400` |
| Text (Muted) | `#64748B` | `--color-text-muted` | `text-slate-500` |
| Accent (Green) | `#22C55E` | `--color-accent` | `text-green-500` |
| Accent (Green Hover) | `#16A34A` | `--color-accent-hover` | `text-green-600` |
| Accent (Green Dim) | `#22C55E20` | `--color-accent-dim` | `bg-green-500/10` |
| Info (Blue) | `#3B82F6` | `--color-info` | `text-blue-500` |
| Warning (Amber) | `#F59E0B` | `--color-warning` | `text-amber-500` |
| Error (Red) | `#EF4444` | `--color-error` | `text-red-500` |
| Success (Emerald) | `#10B981` | `--color-success` | `text-emerald-500` |

**Color Notes:** Dark IDE aesthetic with green accent for AI/execution actions. Blue for information, Amber for warnings, Red for errors. All colors tested for WCAG AA contrast on dark backgrounds.

### Typography

- **Heading Font:** Fira Code (monospace, technical feel)
- **Body Font:** Fira Sans (clean, readable)
- **Code Font:** Fira Code (inline code, terminal output)
- **Mood:** Technical, precise, intelligent, trustworthy

**Google Fonts:**
```
https://fonts.google.com/share?selection.family=Fira+Code:wght@400;500;600;700|Fira+Sans:wght@300;400;500;600;700
```

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

**Type Scale:**

| Element | Font | Size | Weight | Line Height |
|---------|------|------|--------|-------------|
| H1 | Fira Code | 28px / 1.75rem | 700 | 1.3 |
| H2 | Fira Code | 22px / 1.375rem | 600 | 1.3 |
| H3 | Fira Code | 18px / 1.125rem | 600 | 1.4 |
| Body | Fira Sans | 14px / 0.875rem | 400 | 1.6 |
| Body Small | Fira Sans | 13px / 0.8125rem | 400 | 1.5 |
| Caption | Fira Sans | 12px / 0.75rem | 400 | 1.5 |
| Code | Fira Code | 13px / 0.8125rem | 400 | 1.6 |
| Button | Fira Sans | 14px / 0.875rem | 500 | 1 |

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps, icon padding |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `12px` / `0.75rem` | Inner card padding |
| `--space-lg` | `16px` / `1rem` | Standard padding |
| `--space-xl` | `24px` / `1.5rem` | Section padding |
| `--space-2xl` | `32px` / `2rem` | Large gaps |
| `--space-3xl` | `48px` / `3rem` | Page margins |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `4px` | Tags, badges |
| `--radius-md` | `8px` | Buttons, inputs |
| `--radius-lg` | `12px` | Cards, panels |
| `--radius-xl` | `16px` | Modals, dialogs |

### Shadow Depths (Dark Mode Optimized)

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | Subtle lift |
| `--shadow-md` | `0 4px 8px rgba(0,0,0,0.4)` | Cards, buttons |
| `--shadow-lg` | `0 8px 16px rgba(0,0,0,0.5)` | Elevated panels |
| `--shadow-xl` | `0 16px 32px rgba(0,0,0,0.6)` | Modals, dialogs |
| `--shadow-glow` | `0 0 20px rgba(34,197,94,0.15)` | Active/focus accent glow |

---

## Layout System

### Application Shell

```
+---------------------------------------------------+
| Title Bar (Tauri draggable region)      [-][M][X]  |
+--------+------------------------------------------+
|        |                                          |
| Side   |  Main Content Area                       |
| bar    |                                          |
| (56px  |  +-----------------------------------+  |
|  or    |  |  Content Panel                    |  |
| 240px) |  |                                   |  |
|        |  +-----------------------------------+  |
|        |                                          |
+--------+------------------------------------------+
|  Status Bar                                       |
+---------------------------------------------------+
```

### Sidebar

- **Collapsed:** 56px wide (icon-only mode)
- **Expanded:** 240px wide
- **Background:** `--color-bg-deep` (#0B0F1A)
- **Active item:** Left 2px accent border + `--color-accent-dim` background
- **Hover:** `--color-surface` background
- **Transition:** width 200ms ease

### Main Views

| View | Layout | Description |
|------|--------|-------------|
| **Chat** | Single column, full height | Primary interaction view |
| **Setup** | Two-column form layout | Configuration panels |
| **Monitor** | Dashboard grid (2-3 cols) | Status cards + charts |
| **Skills** | Grid/List toggle | Skill browser |

---

## Component Specs

### Buttons

```css
/* Primary Button (Accent Green) */
.btn-primary {
  background: #22C55E;
  color: #0F172A;
  padding: 8px 16px;
  border-radius: 8px;
  font-family: 'Fira Sans', sans-serif;
  font-size: 14px;
  font-weight: 500;
  border: none;
  transition: background-color 200ms ease;
  cursor: pointer;
}
.btn-primary:hover { background: #16A34A; }
.btn-primary:disabled { background: #334155; color: #64748B; cursor: not-allowed; }

/* Secondary Button (Ghost) */
.btn-secondary {
  background: transparent;
  color: #F8FAFC;
  padding: 8px 16px;
  border: 1px solid #334155;
  border-radius: 8px;
  font-family: 'Fira Sans', sans-serif;
  font-size: 14px;
  font-weight: 500;
  transition: all 200ms ease;
  cursor: pointer;
}
.btn-secondary:hover { background: #1E293B; border-color: #64748B; }

/* Icon Button */
.btn-icon {
  background: transparent;
  color: #94A3B8;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: none;
  transition: all 200ms ease;
  cursor: pointer;
}
.btn-icon:hover { background: #1E293B; color: #F8FAFC; }
```

### Cards

```css
.card {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 16px;
  transition: border-color 200ms ease;
}
.card:hover { border-color: #64748B; }
.card-header { font-family: 'Fira Code', monospace; font-size: 14px; font-weight: 600; color: #F8FAFC; }
.card-body { font-family: 'Fira Sans', sans-serif; font-size: 13px; color: #94A3B8; line-height: 1.6; }
```

### Inputs

```css
.input {
  background: #0F172A;
  color: #F8FAFC;
  padding: 10px 12px;
  border: 1px solid #334155;
  border-radius: 8px;
  font-family: 'Fira Sans', sans-serif;
  font-size: 14px;
  transition: border-color 200ms ease;
}
.input:focus {
  border-color: #22C55E;
  outline: none;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.15);
}
.input::placeholder { color: #64748B; }
```

### Chat Bubbles

```css
/* AI Message */
.chat-ai {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 12px 12px 12px 4px;
  padding: 12px 16px;
  color: #F8FAFC;
  max-width: 80%;
}

/* User Message */
.chat-user {
  background: #22C55E15;
  border: 1px solid #22C55E30;
  border-radius: 12px 12px 4px 12px;
  padding: 12px 16px;
  color: #F8FAFC;
  max-width: 80%;
  margin-left: auto;
}
```

### Tags / Badges

```css
.tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  font-weight: 500;
}
.tag-green { background: #22C55E20; color: #22C55E; }
.tag-blue { background: #3B82F620; color: #3B82F6; }
.tag-amber { background: #F59E0B20; color: #F59E0B; }
.tag-red { background: #EF444420; color: #EF4444; }
```

### Status Indicators

```css
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.status-online { background: #22C55E; box-shadow: 0 0 6px rgba(34, 197, 94, 0.4); }
.status-busy { background: #F59E0B; box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }
.status-error { background: #EF4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }
.status-offline { background: #64748B; }
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}
.modal {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-xl);
  max-width: 480px;
  width: 90%;
}
```

### Code Blocks / Terminal

```css
.code-block {
  background: #0B0F1A;
  border: 1px solid #1E293B;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #E2E8F0;
  line-height: 1.6;
  overflow-x: auto;
}
```

---

## Icons

- **Library:** Lucide React (https://lucide.dev)
- **Size:** 20px default, 16px compact, 24px large
- **Stroke:** 1.5px (matches Lucide default)
- **Color:** Inherit from parent text color

**Key Icons Mapping:**

| Context | Icon | Lucide Name |
|---------|------|-------------|
| Chat | Message bubble | `MessageSquare` |
| Settings | Gear | `Settings` |
| Monitor | Activity | `Activity` |
| Skills | Puzzle | `Puzzle` |
| Brain/AI | Brain | `Brain` |
| Memory | Database | `Database` |
| Tools | Wrench | `Wrench` |
| Terminal | Terminal | `Terminal` |
| Send | Arrow up | `ArrowUp` |
| Status OK | Check circle | `CheckCircle` |
| Warning | Alert triangle | `AlertTriangle` |
| Error | X circle | `XCircle` |
| Expand | Panel left | `PanelLeft` |
| Collapse | Panel left close | `PanelLeftClose` |

---

## Animation & Transitions

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Hover | 200ms | ease | Button, card, link hover |
| Focus | 200ms | ease | Input focus ring |
| Sidebar | 200ms | ease | Expand/collapse |
| Modal | 250ms | ease-out | Open/close |
| Toast | 300ms | ease-out | Slide in notification |
| Loading | 1000ms | ease-in-out | Pulse/skeleton |

**Reduced Motion:**
```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop Large | >= 1440px | Full sidebar + main content |
| Desktop | >= 1024px | Full sidebar + main content |
| Tablet | >= 768px | Collapsed sidebar + main content |
| Mobile | < 768px | Bottom nav + full-width content |

**Note:** As a Tauri desktop app, the primary target is >= 1024px. Tablet/Mobile layouts are for window resizing scenarios.

---

## Anti-Patterns (Do NOT Use)

- No emojis as icons -- use SVG icons (Lucide)
- No missing cursor:pointer on clickable elements
- No layout-shifting hover effects (scale transforms that shift siblings)
- No low contrast text (maintain 4.5:1 minimum)
- No instant state changes (always use 200ms transitions)
- No invisible focus states
- No white backgrounds in dark mode
- No light mode component specs mixed in (this is dark-mode-only)
- No generic sans-serif (always specify Fira Sans / Fira Code)
- No border-radius > 16px (keep it professional, not bubbly)

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use Lucide SVG)
- [ ] All icons from Lucide React, consistent sizing
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (200ms)
- [ ] Dark mode text contrast >= 4.5:1
- [ ] Focus states visible (green glow ring)
- [ ] `prefers-reduced-motion` respected
- [ ] Sidebar collapse/expand works
- [ ] No content hidden behind fixed elements
- [ ] Code blocks use Fira Code monospace
- [ ] Status indicators use correct semantic colors
- [ ] Loading states for async operations
