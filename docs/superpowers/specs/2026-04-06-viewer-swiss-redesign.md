# Viewer Redesign: Swiss International / Clinical Precision

**Date:** 2026-04-06
**Status:** Approved
**Scope:** Visual redesign of both live and static session viewers

## Design Direction

Swiss International Style with clinical precision. The viewer should feel like a scholarly reference tool — authoritative, clean, typographically driven. Content is freed from containers and boxes. Visual hierarchy comes from typography, spacing, color, and divider lines — not from borders, backgrounds, or card components.

Icons are retained for space efficiency (Lucide stroke icons, color-coded by tool type).

## Design Principles

1. **No enclosure without purpose.** Remove Card wrappers, bordered boxes, rounded containers, and background fills unless they serve a specific interactive function (e.g., popovers need boundaries).
2. **Divider lines as structure.** Horizontal rules between feed items. Thin rules between content sections. This is the primary structural vocabulary.
3. **Typography carries hierarchy.** Size, weight, case, and tracking distinguish levels — not background color or borders. Headers are bold and uppercase-tracked; metadata is small and muted.
4. **Color is semantic, not decorative.** Dataset colors (blue=DPRR, green=Nomisma, etc.) appear as text color on labels and icons, never as background fills on badges or pills.
5. **Generous but intentional spacing.** Content breathes, but whitespace is structured on a consistent scale.

## Component Specifications

### Header (both live and static)

**Current:** Two-tier sticky header. Glassmorphism blur, muted background, bordered bottom. First tier: title + connection status + actions. Second tier: filter chips.

**New:** Single-line sticky header. No blur, no background fill. Bottom rule only.

- Left: title (`linked-past`) in 13px, semibold, uppercase, tracked
- Left (adjacent): connection status as colored text (green "Connected" / muted "Disconnected")
- Right: item count in muted tabular-nums, filter toggle icon, expand/collapse icons
- Bottom: 1px rule in `border` color
- Filters: hidden by default, revealed as a second row when filter icon is toggled. Same single-rule separation.

### Feed Items

**Current:** Bordered rounded boxes (`border rounded-lg`) with muted background header (`bg-muted/50`). Colored circle icons with letter inside. Content wrapped in `p-3` padding.

**New:** Divider-separated rows. No border, no background, no rounded corners.

**Collapsed state:**
- Single row between horizontal rules
- Left to right: Lucide stroke icon (14px, tool-type color) → tool name (13px, medium weight) → dataset label (text-only, dataset color, 10px uppercase tracked) → timestamp (11px, muted, tabular-nums) → chevron-right (12px, muted)
- Padding: `py-2.5 px-0` (content sits at page margins)
- Bottom border: `border-b border-border`

**Expanded state:**
- Header row identical to collapsed, chevron rotated 90deg
- Content flows below, indented left by 24px (aligns with text after icon)
- No card wrapper, no background, no additional border around content
- Bottom border on the outer container, not on the header

**Color mapping (unchanged semantically, different rendering):**
- query → blue (`text-blue-400`)
- search → violet (`text-violet-400`)
- entity → emerald (`text-emerald-400`)
- links → amber (`text-amber-400`)
- report → rose (`text-rose-400`)

### Entity Content (inside expanded feed items)

**Current:** Card component (`rounded-xl`, `ring-1`, padded sections). Header with dataset badge pill. Properties in tight grid.

**New:** Flush content, no card.

- Dataset label + type breadcrumb on first line (e.g., `DPRR  Person › Senator`)
- Entity name as 16px semibold, negative letter-spacing, with generous margin below
- Properties as definition grid: `grid-cols-[100px_1fr]`, 12px. Property names in muted semibold. Values in default foreground.
- Section breaks: thin top rule + uppercase tracked section label (11px, muted, semibold). Sections: identifiers, roles/offices, relationships, cross-references.

### Data Tables (SPARQL results)

**Current:** Table with bordered rows, `hover:bg-muted/50`, resize handles, toolbar above.

**New:** Minimal table, no outer container.

- Header row: bold, uppercase, smaller size (10px tracked), no background fill. Bottom border only (slightly heavier than row dividers).
- Body rows: 12px, thin bottom border (`border-border`). No hover background.
- Cell padding: `px-3 py-2`
- URIs and literal values in monospace where appropriate
- Toolbar (wrap toggle, column visibility): remains above table, right-aligned, ghost buttons
- Footer (row count, copy): remains below, muted text

### Dataset Badges

**Current:** Solid colored pills (`bg-blue-500 text-white`, rounded, padded).

**New:** Text-only colored labels.

- Dataset name in its signature color
- 10px, font-weight 500, uppercase, letter-spacing 0.05em
- No background, no border, no pill shape
- Appears inline in feed item rows and entity content headers

### Entity URI Links

**Current:** Colored background tint pills with rounded corners, popover on hover.

**New:** Plain inline links.

- URI text in dataset color, no background, no pill/rounded shape
- Underline on hover
- Popover behavior preserved (hover/click to see entity preview)
- Should read like hyperlinks in a document

### Search Results

**Current:** Left border accent (`border-l-2`), `space-y-0.5`, hover background.

**New:** Consistent with feed vocabulary.

- Results listed with thin bottom borders between items
- No left border accent
- Dataset group headers: text-only dataset label (colored, uppercase) + count
- Individual results: entity name as link, type breadcrumb in muted text
- No hover background change

### Cross-References (XrefList)

**Current:** Space between groups, colored confidence badges, left border accent per group.

**New:** Flat list with section breaks.

- Confidence groups separated by thin rules + uppercase section label
- No left border accent
- Relationship items: predicate label → target link → basis text, all inline
- Confidence level as muted text label, not a colored badge

### Markdown Reports

**Current:** `prose` container, centered `max-w-3xl`, custom heading/list spacing.

**New:** Mostly unchanged — prose styling is already clean.

- Remove `max-w-3xl` constraint (let content match feed width)
- Keep `prose dark:prose-invert` typography
- Code blocks: keep `bg-muted rounded p-3` (acceptable container — it's a code block)
- Tables in markdown: match the data table spec above

### Drop Zone (static viewer entry)

**Current:** Dashed-border box with upload icon and instructional text.

**New:** Centered minimal prompt.

- Vertically centered in viewport
- Subtle dashed outline (`border-dashed border-border`)
- Instruction text: 14px, muted. "Drop a session file or paste a gist URL"
- No heavy iconography — a single small upload icon (14px) is acceptable
- Drag-over state: dashed border becomes solid, text color brightens

### Popovers (entity preview on URI hover)

**Current:** Card component inside popover.

**New:** Popover retains a container (popovers need visual boundaries to float over content).

- Light border (`border border-border`), small shadow, `rounded-lg`
- No Card component — just a styled div
- Content follows the flush entity layout (grid properties, section rules)
- This is the one place where a container is justified

## Typography Scale

| Role | Size | Weight | Case | Tracking | Color |
|------|------|--------|------|----------|-------|
| Page title | 13px | 600 | Uppercase | 0.02em | foreground |
| Feed item label | 13px | 500 | Normal | Normal | foreground |
| Entity name | 16px | 600 | Normal | -0.01em | foreground |
| Section heading | 11px | 600 | Uppercase | 0.05em | muted |
| Property name | 12px | 500 | Normal | Normal | muted |
| Property value | 12px | 400 | Normal | Normal | foreground |
| Dataset label | 10px | 500 | Uppercase | 0.05em | dataset color |
| Timestamp | 11px | 400 | Normal | Normal | muted, tabular-nums |
| Metadata/count | 11px | 400 | Normal | Normal | muted |

## Spacing Scale

Use a consistent 4px base: 4, 8, 12, 16, 20, 24, 32.

- Feed page padding: 20px horizontal
- Between feed items: 0 (dividers handle separation, padding is on the items)
- Feed item row padding: 10px vertical
- Expanded content indent: 24px left
- Section gap inside entity: 14px margin-top on rules
- Property grid: 6px row gap, 16px column gap

## Files to Modify

| File | Change |
|------|--------|
| `src/components/feed-item.tsx` | Remove border/rounded/bg-muted, add divider lines, restructure collapsed/expanded |
| `src/components/entity-card.tsx` | Remove Card wrapper, flush grid layout, section rules |
| `src/components/viewer-layout.tsx` | Single-line header, remove blur/background, toggleable filters |
| `src/components/dataset-badge.tsx` | Text-only colored label, remove bg/pill |
| `src/components/entity-uri.tsx` | Plain inline link, remove pill styling |
| `src/components/data-table.tsx` | Remove hover bg, typographic headers, minimal borders |
| `src/components/search-results.tsx` | Remove left border accent, use dividers |
| `src/components/xref-list.tsx` | Remove left border, flat sections with rules |
| `src/components/markdown-report.tsx` | Remove max-w-3xl, align table styles |
| `src/components/drop-zone.tsx` | Minimal centered prompt |
| `src/components/feed-filters.tsx` | Restyle as toggleable row, consistent with header |
| `src/components/entity-popover.tsx` | Replace Card with styled div |
| `src/components/query-result.tsx` | Ensure no wrapping container |
| `src/entries/static.tsx` | Update header to match new single-line pattern |
| `src/components/ui/card.tsx` | May become unused — keep for now, remove if no imports remain |

## What Does NOT Change

- Component logic, state management, hooks — purely visual
- Collapsible behavior (still uses Collapsible primitive)
- Popover behavior (still triggers on hover/click)
- Dark mode support (all changes use semantic tokens)
- Responsive behavior
- Filter functionality (just the toggle pattern changes)
- Bookmark/notes features in live viewer
