# Viewer Swiss Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the linked-past session viewer from boxed/card-based UI to Swiss International / clinical precision style using divider lines, flush content, and typographic hierarchy.

**Architecture:** Purely visual changes — no component logic, state, hooks, or data flow changes. Each task modifies one component's className strings and JSX structure. Components are changed leaf-first (smallest dependencies first) so each commit produces a working UI.

**Tech Stack:** React 19, Tailwind CSS 4, Lucide React icons, shadcn/ui primitives (Collapsible, Popover, Table — keeping these; removing Card usage)

**Spec:** `docs/superpowers/specs/2026-04-06-viewer-swiss-redesign.md`

---

### Task 1: Dataset Badge — text-only colored labels

**Files:**
- Modify: `packages/linked-past-viewer/src/components/dataset-badge.tsx`
- Modify: `packages/linked-past-viewer/src/lib/datasets.ts` (add missing RPC entry)

This is a leaf component used by FeedItem, EntityCard, EntityPopoverContent, and SearchResults. Change it first so all consumers inherit the new style.

- [ ] **Step 1: Replace the pill trigger with a text-only label**

In `dataset-badge.tsx`, replace the PopoverTrigger className. The current trigger is:

```tsx
<PopoverTrigger
  className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white cursor-pointer ${color}`}
  onMouseEnter={() => setOpen(true)}
  onMouseLeave={() => setOpen(false)}
>
  {dataset}
</PopoverTrigger>
```

Replace with:

```tsx
<PopoverTrigger
  className="cursor-pointer"
  onMouseEnter={() => setOpen(true)}
  onMouseLeave={() => setOpen(false)}
>
  <span
    className="text-[10px] font-medium uppercase tracking-widest"
    style={{ color: textColor }}
  >
    {dataset}
  </span>
</PopoverTrigger>
```

- [ ] **Step 2: Replace the color mapping**

The current `COLORS` object maps dataset names to Tailwind bg classes (`bg-blue-500`, etc.). Replace it with a text color mapping. Remove the old `COLORS` object and add:

```tsx
const TEXT_COLORS: Record<string, string> = {
  dprr: "#60a5fa",     // blue-400
  pleiades: "#4ade80",  // green-400 (preserves existing green association)
  periodo: "#c084fc",   // violet-400
  nomisma: "#facc15",   // yellow-400 (preserves existing yellow association)
  crro: "#fb923c",      // orange-400
  ocre: "#f87171",      // red-400
  edh: "#22d3ee",       // cyan-400 (preserves existing cyan association)
  rpc: "#2dd4bf",       // teal-400
};
```

Also add RPC to `src/lib/datasets.ts` (currently missing). Add this entry to the `DATASETS` record:

```tsx
rpc: {
  name: "Roman Provincial Coinage Online",
  description: "Provincial mint coinage (44 BC – 296 AD) with Nomisma links",
  license: "ODbL 1.0",
  url: "https://rpc.ashmus.ox.ac.uk",
},
```

Update the component to use it:

```tsx
const textColor = TEXT_COLORS[dataset.toLowerCase()] ?? "#a1a1aa";
```

Remove the old `const color = COLORS[...]` line.

- [ ] **Step 2b: Update the no-info fallback branch**

The early-return branch at line 24-30 for unknown datasets still uses the old pill styling:

```tsx
if (!info) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white ${color}`}>
      {dataset}
    </span>
  );
}
```

Replace with the text-only style:

```tsx
if (!info) {
  return (
    <span
      className="text-[10px] font-medium uppercase tracking-widest"
      style={{ color: textColor }}
    >
      {dataset}
    </span>
  );
}
```

- [ ] **Step 3: Verify in browser**

Run `BUILD_STATIC=1 pnpm run dev` and open http://localhost:5173/linked-past/viewer/. Load a session file. Verify dataset labels appear as colored uppercase text without background pills. Popover should still appear on hover.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/dataset-badge.tsx
git commit -m "style(viewer): dataset badges as text-only colored labels"
```

---

### Task 2: Entity URI — plain inline links

**Files:**
- Modify: `packages/linked-past-viewer/src/components/entity-uri.tsx`

Another leaf component used by SearchResults, XrefList, MarkdownReport, and QueryResult.

- [ ] **Step 1: Replace PILL_CLASSES with inline link classes**

Find the `PILL_CLASSES` constant:

```tsx
const PILL_CLASSES =
  "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium cursor-pointer transition-[filter] hover:brightness-95 dark:hover:brightness-110";
```

Replace with:

```tsx
const LINK_CLASSES =
  "text-xs font-medium cursor-pointer hover:underline underline-offset-2";
```

- [ ] **Step 2: Update the `pill` const that uses PILL_CLASSES**

`PILL_CLASSES` is used in one place — the `pill` const (line 34-38) which is then reused in both the static return and the popover branch. Rename it:

```tsx
const link = (
  <span className={LINK_CLASSES} style={datasetStyle(dataset)}>
    {label}
  </span>
);
```

Update all references from `pill` to `link` throughout the component.

- [ ] **Step 3: Fix `datasetStyle` to remove backgroundColor**

The `datasetStyle` function (line 16-22) currently sets both `backgroundColor` and `color`:

```tsx
function datasetStyle(dataset: string | null): React.CSSProperties {
  const ds = dataset ?? "default";
  return {
    backgroundColor: `var(--ds-${ds}-bg, var(--ds-default-bg))`,
    color: `var(--ds-${ds}-fg, var(--ds-default-fg))`,
  };
}
```

Remove the `backgroundColor` line — entity URIs should be plain colored text with no background:

```tsx
function datasetStyle(dataset: string | null): React.CSSProperties {
  const ds = dataset ?? "default";
  return {
    color: `var(--ds-${ds}-fg, var(--ds-default-fg))`,
  };
}
```

- [ ] **Step 4: Verify in browser**

Check that entity URIs render as colored text links that underline on hover. Popovers should still work. No background tint or rounded pill shape.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/entity-uri.tsx
git commit -m "style(viewer): entity URIs as plain inline links"
```

---

### Task 3: Connection Status — minimal text

**Files:**
- Modify: `packages/linked-past-viewer/src/components/connection-status.tsx`

Tiny leaf component. Quick win.

- [ ] **Step 1: Simplify to match header spec**

The current component renders an icon + text label. Keep the same structure but ensure sizing matches the spec (11px text). The current implementation is already close. Verify the className:

```tsx
<span className={`inline-flex items-center gap-1 text-xs ${
  connected ? "text-green-600 dark:text-green-400" : "text-red-500"
}`}>
```

Change `text-xs` to `text-[11px]` for precise spec alignment:

```tsx
<span className={`inline-flex items-center gap-1.5 text-[11px] ${
  connected ? "text-green-600 dark:text-green-400" : "text-red-500"
}`}>
```

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past-viewer/src/components/connection-status.tsx
git commit -m "style(viewer): connection status text size to 11px"
```

---

### Task 4: Feed Filters — toggleable row, restyled chips

**Files:**
- Modify: `packages/linked-past-viewer/src/components/feed-filters.tsx`

The filters component itself doesn't change structurally — it still renders ToggleChips. But the chip styling needs to match the new vocabulary. The parent components (viewer-layout, static.tsx) will control filter visibility via a toggle icon — that toggle behavior is implemented later in Tasks 13 and 14. This task only handles the chip restyling.

- [ ] **Step 1: Restyle ToggleChip**

Find the `ToggleChip` component. The current active/inactive classes are:

```tsx
className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border cursor-pointer transition-colors select-none ${
  active
    ? "bg-primary text-primary-foreground border-primary"
    : "bg-transparent text-muted-foreground border-border hover:border-foreground/30"
}`}
```

Replace with a cleaner style — no border, no background. Active state uses foreground color, inactive uses muted:

```tsx
className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium cursor-pointer transition-colors select-none ${
  active
    ? "text-foreground"
    : "text-muted-foreground/60 hover:text-muted-foreground"
}`}
```

- [ ] **Step 2: Remove colored circle icons from type chips**

In the `TYPE_OPTIONS` mapping section, the icon is rendered inside a colored circle:

```tsx
icon={<span className={`inline-flex items-center justify-center w-4 h-4 rounded-full ${meta.bg} ${meta.color}`}>{meta.icon}</span>}
```

Replace with just the icon in the type color (no circle):

```tsx
icon={<span className={meta.color}>{meta.icon}</span>}
```

- [ ] **Step 3: Replace separator style**

The current separator between filter groups is:

```tsx
<span className="text-muted-foreground/40">|</span>
```

Replace with a thinner visual separator:

```tsx
<span className="text-border">·</span>
```

- [ ] **Step 4: Verify in browser**

Filters should appear as minimal text toggles — active ones in foreground color, inactive ones muted. No borders or backgrounds on chips.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/feed-filters.tsx
git commit -m "style(viewer): minimal filter chips without borders"
```

---

### Task 5: Feed Item — divider lines, flush layout

**Files:**
- Modify: `packages/linked-past-viewer/src/components/feed-item.tsx`

This is the core visual change. Replace bordered boxes with divider-separated rows.

- [ ] **Step 1: Replace the outer Collapsible className**

Current:

```tsx
<Collapsible
  open={open}
  onOpenChange={setOpen}
  className={`border rounded-lg mb-3 overflow-hidden ${bookmarked ? "ring-2 ring-primary/30" : ""}`}
>
```

Replace with:

```tsx
<Collapsible
  open={open}
  onOpenChange={setOpen}
  className={`border-b border-border ${bookmarked ? "bg-primary/[0.02]" : ""}`}
>
```

- [ ] **Step 2: Replace the header row**

Current header:

```tsx
<div className="flex items-center gap-2 px-3 py-2 bg-muted/50 text-sm">
```

Replace with:

```tsx
<div className="flex items-center gap-2.5 py-2.5 text-sm">
```

No background, no horizontal padding (parent provides page-level padding).

- [ ] **Step 3: Replace the icon rendering**

Current icon inside CollapsibleTrigger:

```tsx
<span className={`shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full ${typeMeta.bg} ${typeMeta.color}`}>
  {typeMeta.icon}
</span>
```

Replace with a plain Lucide icon (the icons are already Lucide components from the `typeMeta` mapping). Remove the colored circle:

```tsx
<span className={`shrink-0 ${typeMeta.color}`}>
  {typeMeta.icon}
</span>
```

Ensure the icon components in the `TYPE_META` mapping use `className="w-3.5 h-3.5"` instead of the current smaller size inside circles.

- [ ] **Step 4: Update the TYPE_META color mapping**

The current mapping uses bg + text color pairs for circles (e.g., `bg-blue-100 dark:bg-blue-950` + `text-blue-600 dark:text-blue-400`). Replace with text-only colors matching the spec:

```tsx
const TYPE_META: Record<string, { icon: React.ReactNode; color: string }> = {
  query: { icon: <Database className="w-3.5 h-3.5" />, color: "text-blue-600 dark:text-blue-400" },
  search: { icon: <Search className="w-3.5 h-3.5" />, color: "text-violet-600 dark:text-violet-400" },
  entity: { icon: <User className="w-3.5 h-3.5" />, color: "text-emerald-600 dark:text-emerald-400" },
  links: { icon: <Link2 className="w-3.5 h-3.5" />, color: "text-amber-600 dark:text-amber-400" },
  report: { icon: <FileText className="w-3.5 h-3.5" />, color: "text-rose-600 dark:text-rose-400" },
};
```

Remove the `bg` and `label` keys from the type. Keep the dual-mode color classes (600 for light, 400 for dark) to ensure readability in both themes.

**Note:** `feed-filters.tsx` has its own copy of TYPE_META. Keep the color values in sync — Task 4 Step 2 references `meta.color` which should use these same dual-mode classes.

- [ ] **Step 5: Replace the chevron**

Current: `ChevronUp` / `ChevronDown` with `w-4 h-4`.

Replace with `ChevronRight` that rotates when open. In the lucide-react import block, add `ChevronRight` and remove `ChevronDown` and `ChevronUp`:

```tsx
<span className={`text-muted-foreground shrink-0 transition-transform ${open ? "rotate-90" : ""}`}>
  <ChevronRight className="w-3 h-3" />
</span>
```

- [ ] **Step 6: Replace the note bar**

Current:

```tsx
<div className="px-3 py-1.5 bg-primary/5 border-b text-xs flex items-start gap-2">
```

Replace with:

```tsx
<div className="py-1.5 pl-6 text-xs flex items-start gap-2">
```

No background, no border. Indented to align with content.

- [ ] **Step 7: Replace the content area**

Current:

```tsx
<CollapsibleContent className="p-3">
```

Replace with:

```tsx
<CollapsibleContent className="pb-4 pl-6">
```

Left padding of 24px (pl-6) to indent content past the icon. No right padding (inherits from page), bottom padding for spacing before the next divider.

- [ ] **Step 8: Update "Add note" button alignment**

The add-note button sits inside CollapsibleContent. Update its margin:

```tsx
<button onClick={...} className="mt-3 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer">
  + Add note
</button>
```

- [ ] **Step 9: Verify in browser**

Feed items should display as divider-separated rows. Collapsed = single line with icon, tool name, dataset label, timestamp, chevron. Expanded = content indented below, no card wrapper. Bookmarked items have a very subtle background tint.

- [ ] **Step 10: Commit**

```bash
git add packages/linked-past-viewer/src/components/feed-item.tsx
git commit -m "style(viewer): feed items as divider-separated rows"
```

---

### Task 6: Entity Card — flush content, no Card wrapper

**Files:**
- Modify: `packages/linked-past-viewer/src/components/entity-card.tsx`

- [ ] **Step 1: Remove Card imports**

Remove:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
```

- [ ] **Step 2: Replace the JSX structure**

Replace the entire return block. Current structure is `<Card> → <CardHeader> → <CardContent>`. New structure is a flat `<div>`:

```tsx
return (
  <div>
    <div className="flex items-baseline gap-2 mb-1">
      {data.dataset && <DatasetBadge dataset={data.dataset} />}
      {data.type_hierarchy && data.type_hierarchy.length > 0 && (
        <span className="text-[11px] text-muted-foreground">
          {data.type_hierarchy.join(" › ")}
        </span>
      )}
    </div>
    <h3 className="text-base font-semibold tracking-tight mb-1">{data.name}</h3>
    <p className="text-xs text-muted-foreground mb-3">{shortUri(data.uri)}</p>
    {data.description && (
      <p className="text-sm text-muted-foreground leading-relaxed mb-3">
        {data.description}
      </p>
    )}

    {visibleProps.length > 0 && (
      <dl className="grid grid-cols-[100px_1fr] gap-x-4 gap-y-1.5 text-xs mb-4">
        {visibleProps.map((p, i) => (
          <div key={i} className="contents">
            <dt className="text-muted-foreground font-medium">
              <PredicateLabel pred={p.pred} meta={meta[p.pred]} />
            </dt>
            <dd className="break-words">
              <PropertyValue value={p.obj} />
              {p.count && p.count > 1 && (
                <span className="text-xs text-muted-foreground ml-1">
                  (+{p.count - 1} more)
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    )}

    {data.see_also && data.see_also.length > 0 && (
      <div className="pt-3 border-t border-border mb-4">
        <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
          See also
        </h4>
        <ul className="space-y-1">
          {data.see_also.map((url, i) => (
            <li key={i} className="text-xs">
              <a
                href={linkHref(url)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                {shortUri(url)}
                <ExternalLink className="w-3 h-3 opacity-60" />
              </a>
            </li>
          ))}
        </ul>
      </div>
    )}

    {data.xrefs.length > 0 && (
      <div className="pt-3 border-t border-border">
        <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
          Cross-references
        </h4>
        <XrefList links={data.xrefs} />
      </div>
    )}
  </div>
);
```

- [ ] **Step 3: Verify in browser**

Expand an entity feed item. Entity data should render directly in the feed flow — no card border, no ring, no rounded corners. Sections separated by thin rules with uppercase labels.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/entity-card.tsx
git commit -m "style(viewer): entity card as flush content without Card wrapper"
```

---

### Task 7: Entity Popover — replace Card with styled div

**Files:**
- Modify: `packages/linked-past-viewer/src/components/entity-popover.tsx`

- [ ] **Step 1: Remove Card imports**

Remove:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
```

- [ ] **Step 2: Replace the JSX structure**

Replace the `<Card>` wrapper with a plain div:

```tsx
return (
  <div className="w-[420px] border border-border rounded-lg shadow-sm bg-background p-3">
    <div className="mb-1">
      <div className="flex items-baseline gap-1.5">
        {data.dataset && <DatasetBadge dataset={data.dataset} />}
        {data.type_hierarchy && data.type_hierarchy.length > 0 && (
          <span className="text-[10px] text-muted-foreground">
            {data.type_hierarchy.join(" › ")}
          </span>
        )}
      </div>
      <h4 className="text-base font-semibold tracking-tight mt-1">{data.name}</h4>
      {data.description && (
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mt-1">
          {data.description}
        </p>
      )}
    </div>

    {topProps.length > 0 && (
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs mt-2">
        {topProps.map((p, i) => (
          <div key={i} className="contents">
            <dt className="font-medium text-muted-foreground">
              {humanizePredicate(p.pred)}
            </dt>
            <ExpandableValue value={p.obj}>
              <PropertyValue value={p.obj} />
            </ExpandableValue>
          </div>
        ))}
      </dl>
    )}

    {(data.xrefs.length > 0 || (data.see_also && data.see_also.length > 0)) && (
      <div className="mt-2 pt-2 border-t border-border text-xs text-muted-foreground flex gap-3">
        {data.xrefs.length > 0 && (
          <span>
            {data.xrefs.length} cross-reference{data.xrefs.length !== 1 ? "s" : ""}
          </span>
        )}
        {data.see_also && data.see_also.length > 0 && (
          <span>
            {data.see_also.length} external link{data.see_also.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    )}
  </div>
);
```

- [ ] **Step 3: Verify in browser**

Hover over an entity URI. Popover should appear with a light border, small shadow, rounded corners — but no Card component ring styling.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/entity-popover.tsx
git commit -m "style(viewer): entity popover as styled div instead of Card"
```

---

### Task 8: Data Table — minimal typographic headers

**Files:**
- Modify: `packages/linked-past-viewer/src/components/data-table.tsx`
- Modify: `packages/linked-past-viewer/src/components/ui/table.tsx`

- [ ] **Step 1: Update table header styling in ui/table.tsx**

Read `src/components/ui/table.tsx` first. Find the `TableHead` component and update its className to remove background, add uppercase tracking:

The header cell should become:

```tsx
className="h-8 px-3 text-left align-middle text-[10px] font-semibold uppercase tracking-widest text-muted-foreground whitespace-nowrap [&:has([role=checkbox])]:pr-0"
```

- [ ] **Step 2: Update table row styling in ui/table.tsx**

Find the `TableRow` component. Current className is:

```tsx
"border-b transition-colors hover:bg-muted/50 has-aria-expanded:bg-muted/50 data-[state=selected]:bg-muted"
```

Replace with no hover and no selection highlight (no row selection is used in the viewer):

```tsx
"border-b border-border transition-colors"
```

- [ ] **Step 3: Update cell styling in ui/table.tsx**

Find `TableCell`. Current className is:

```tsx
"p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0"
```

Update padding but **keep `whitespace-nowrap`** — the wrap/truncate toggle in `data-table.tsx` conditionally adds `whitespace-normal break-words` and needs this as the base state:

```tsx
"px-3 py-2 align-middle text-xs whitespace-nowrap [&:has([role=checkbox])]:pr-0"
```

- [ ] **Step 4: Verify in browser**

Load a session with a query result. Table headers should be small, uppercase, tracked, no background. Rows should have thin dividers, no hover effect.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/data-table.tsx packages/linked-past-viewer/src/components/ui/table.tsx
git commit -m "style(viewer): minimal data table with typographic headers"
```

---

### Task 9: Search Results — divider style

**Files:**
- Modify: `packages/linked-past-viewer/src/components/search-results.tsx`

- [ ] **Step 1: Remove left border accent and hover**

Replace the results container:

```tsx
<div className="space-y-0.5 ml-1 border-l-2 border-muted pl-3">
```

With:

```tsx
<div>
```

Replace each result row:

```tsx
<div key={i} className="py-1 flex items-baseline gap-2 text-sm hover:bg-muted/30 rounded px-1 -mx-1">
```

With:

```tsx
<div key={i} className="py-1.5 flex items-baseline gap-2 text-sm border-b border-border last:border-0">
```

- [ ] **Step 2: Update the dataset group header**

Replace:

```tsx
<div className="flex items-center gap-2 mb-2">
  <DatasetBadge dataset={ds} />
  <span className="text-xs text-muted-foreground">
    {dsLabel} — {results.length} result{results.length !== 1 ? "s" : ""}
  </span>
</div>
```

With (note: the `{dsLabel} —` prefix is dropped since DatasetBadge already shows the dataset name — this is a minor content simplification):

```tsx
<div className="flex items-baseline gap-2 mb-1">
  <DatasetBadge dataset={ds} />
  <span className="text-[11px] text-muted-foreground">
    {results.length} result{results.length !== 1 ? "s" : ""}
  </span>
</div>
```

- [ ] **Step 3: Verify in browser**

Search results should show as divider-separated items under colored dataset labels. No left border accent, no hover background.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/search-results.tsx
git commit -m "style(viewer): search results with divider lines"
```

---

### Task 10: Cross-References — flat sections

**Files:**
- Modify: `packages/linked-past-viewer/src/components/xref-list.tsx`

- [ ] **Step 1: Remove Badge import and left border**

Remove:

```tsx
import { Badge } from "@/components/ui/badge";
```

Replace the confidence group header:

```tsx
<Badge className={`text-[10px] mb-1 ${color}`}>
  {conf} ({items.length})
</Badge>
```

With a text label:

```tsx
<span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">
  {conf} ({items.length})
</span>
```

Replace the items container:

```tsx
<div className="space-y-1 pl-2 border-l-2">
```

With:

```tsx
<div className="space-y-1 mt-1">
```

- [ ] **Step 2: Add thin rule between confidence groups**

Replace the outer container spacing. Current:

```tsx
<div className="space-y-3">
```

Replace with:

```tsx
<div className="divide-y divide-border">
```

And wrap each group's inner content with padding:

```tsx
<div key={conf} className="py-2 first:pt-0">
```

- [ ] **Step 3: Remove the CONFIDENCE_COLORS mapping**

It's no longer used since we removed the Badge. Delete the entire `CONFIDENCE_COLORS` object.

- [ ] **Step 4: Verify in browser**

Cross-references should appear as flat sections separated by thin rules. Confidence level as muted uppercase text, no colored badges, no left border.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/xref-list.tsx
git commit -m "style(viewer): cross-references as flat sections with rules"
```

---

### Task 11: Markdown Report — remove max-width

**Files:**
- Modify: `packages/linked-past-viewer/src/components/markdown-report.tsx`

- [ ] **Step 1: Remove max-width and adjust container**

Replace:

```tsx
<div className="space-y-4 px-6 py-4 max-w-3xl mx-auto">
```

With:

```tsx
<div className="space-y-4 py-4">
```

No horizontal padding (parent feed item provides indent). No max-width. No centering.

- [ ] **Step 2: Update inline table styles**

In the markdown `components` prop, update `th` to remove background:

Replace:

```tsx
th: ({ children }) => (
  <th className="text-left p-1.5 border-b-2 font-semibold bg-muted/50">{children}</th>
)
```

With:

```tsx
th: ({ children }) => (
  <th className="text-left p-1.5 border-b-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{children}</th>
)
```

- [ ] **Step 3: Verify in browser**

Markdown reports should fill the feed width. Tables inside reports should have typographic headers matching the data table style.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/markdown-report.tsx
git commit -m "style(viewer): markdown report full-width, typographic table headers"
```

---

### Task 12: Drop Zone — minimal entry screen

**Files:**
- Modify: `packages/linked-past-viewer/src/components/drop-zone.tsx`

- [ ] **Step 1: Simplify the layout**

Replace the entire return JSX. Current has a large title, icon-heavy drop area, and paste section. New version is minimal:

```tsx
return (
  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 px-4">
    <div
      className={`w-full max-w-md border border-dashed rounded-lg p-16 text-center cursor-pointer transition-colors ${
        isDragging
          ? "border-foreground text-foreground"
          : "border-border text-muted-foreground hover:border-muted-foreground"
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleFileSelect}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".jsonl"
        className="hidden"
        onChange={handleFileChange}
      />
      <div className="flex flex-col items-center gap-3">
        <Upload className="w-4 h-4" />
        <p className="text-sm">
          {isDragging ? "Drop to load" : "Drop a session file or click to browse"}
        </p>
      </div>
    </div>

    <button
      onClick={() => setShowPaste(!showPaste)}
      className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
    >
      {showPaste ? "Hide paste area" : "Or paste JSONL content"}
    </button>

    {showPaste && (
      <div className="w-full max-w-md space-y-3">
        <textarea
          className="w-full h-32 border border-border rounded-lg bg-transparent px-3 py-2 text-xs font-mono resize-y focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder='{"session_id":"...","seq":1,"type":"query",...}'
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
        />
        <button
          onClick={handlePasteLoad}
          disabled={!pasteText.trim()}
          className="w-full py-2 text-xs font-medium border border-border rounded-lg hover:bg-muted disabled:opacity-40 cursor-pointer transition-colors"
        >
          Load session
        </button>
      </div>
    )}
  </div>
);
```

- [ ] **Step 2: Remove unused imports**

Remove `ClipboardPaste`, `FileText` from lucide-react imports (keep `Upload`). Remove `Button` import from ui/button.

- [ ] **Step 3: Verify in browser**

The entry screen should be a minimal centered prompt with a subtle dashed border, small upload icon, and quiet instruction text.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/drop-zone.tsx
git commit -m "style(viewer): minimal drop zone entry screen"
```

---

### Task 13: Viewer Layout (live) — single-line header

**Files:**
- Modify: `packages/linked-past-viewer/src/components/viewer-layout.tsx`

- [ ] **Step 1: Add filter toggle state**

Add a new state variable after the existing state declarations:

```tsx
const [showFilters, setShowFilters] = useState(false);
```

Import `SlidersHorizontal` from lucide-react for the filter toggle icon.

- [ ] **Step 2: Replace the header**

Replace the entire `<header>` block. Current has two tiers with blur. New is a single line:

```tsx
<header className="sticky top-0 z-50 border-b border-border bg-background">
  <div className="flex items-center gap-3 px-5 h-10 text-sm">
    <span className="text-[13px] font-semibold uppercase tracking-wide">
      linked-past
    </span>
    <ConnectionStatus connected={isConnected} />
    {isViewingPast && (
      <span className="text-[11px] text-yellow-600 dark:text-yellow-400 font-medium">
        past session
      </span>
    )}
    <span className="ml-auto flex items-center gap-3">
      <SessionPicker
        onLoadSession={handleLoadSession}
        onBackToLive={handleBackToLive}
        viewingSessionId={isViewingPast ? pastSession.id : null}
        initialSessionId={initialSessionId}
      />
      {activeMessages.length > 0 && (
        <button
          onClick={() => setShowFilters((v) => !v)}
          className={`text-muted-foreground hover:text-foreground cursor-pointer transition-colors ${showFilters ? "text-foreground" : ""}`}
          title="Toggle filters"
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
        </button>
      )}
      {activeMessages.length > 0 && (
        <ExpandCollapseButtons
          onExpandAll={() => setForceOpen((prev) => ({ value: true, rev: (prev?.rev ?? 0) + 1 }))}
          onCollapseAll={() => setForceOpen((prev) => ({ value: false, rev: (prev?.rev ?? 0) + 1 }))}
        />
      )}
      <AutoScrollButton active={autoScroll} onClick={() => setAutoScroll((prev) => !prev)} />
      <ExportButton messages={filtered} notes={notes} />
      <Button
        variant="ghost"
        size="icon-xs"
        title="Export session as JSONL"
        disabled={!liveSessionId && !pastSession}
        onClick={handleExportJsonl}
      >
        <FileDown className="h-3.5 w-3.5" />
      </Button>
      <DarkModeToggle />
      <span className="text-muted-foreground text-[11px] tabular-nums">
        {filtered.length}/{activeMessages.length}
      </span>
    </span>
  </div>
  {showFilters && activeMessages.length > 0 && (
    <div className="px-5 py-1.5 border-t border-border">
      <FeedFilters
        messages={activeMessages}
        filters={filters}
        bookmarkCount={bookmarks.size}
        onChange={setFilters}
      />
    </div>
  )}
</header>
```

- [ ] **Step 3: Update main content padding**

Replace:

```tsx
<main className="px-4 py-6">
```

With:

```tsx
<main className="px-5 py-4">
```

- [ ] **Step 4: Verify in browser**

Start the live viewer (`pnpm run dev`) with the MCP server running. Header should be a single line — title, connection status, actions. Filter icon toggles a second row. No blur, no background fill.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/viewer-layout.tsx
git commit -m "style(viewer): single-line header with toggleable filters"
```

---

### Task 14: Static Entry — single-line header

**Files:**
- Modify: `packages/linked-past-viewer/src/entries/static.tsx`

- [ ] **Step 1: Add filter toggle state**

Add after the existing state declarations:

```tsx
const [showFilters, setShowFilters] = useState(false);
```

Import `SlidersHorizontal` from lucide-react.

- [ ] **Step 2: Replace the header**

Replace the entire `<header>` block in the loaded-session return. Current has blur + two tiers. New matches the live viewer pattern:

```tsx
<header className="sticky top-0 z-10 border-b border-border bg-background">
  <div className="flex items-center gap-3 px-5 h-10">
    <span className="text-[13px] font-semibold uppercase tracking-wide">
      linked-past
    </span>
    {isGistMode && gist.sessions.length > 1 && (
      <Select value={selectedFilename ?? ""} onValueChange={handleSessionChange}>
        <SelectTrigger size="sm" className="min-w-[160px] text-xs">
          <span className="flex flex-1 text-left truncate">
            {selectedFilename ?? "Select session"}
          </span>
        </SelectTrigger>
        <SelectContent align="start" alignItemWithTrigger={false}>
          {gist.sessions.map((s) => (
            <SelectItem key={s.filename} value={s.filename}>
              {s.filename.replace(/\.jsonl$/, "")} · {s.result.messages.length} items
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )}
    {isGistMode && gist.sessions.length === 1 && (
      <span className="text-[11px] text-muted-foreground">
        {gist.sessions[0].filename.replace(/\.jsonl$/, "")}
      </span>
    )}
    <span className="ml-auto flex items-center gap-3">
      <span className="text-[11px] text-muted-foreground tabular-nums">
        {filtered.length}/{session.messages.length}
      </span>
      {session.messages.length > 0 && (
        <button
          onClick={() => setShowFilters((v) => !v)}
          className={`text-muted-foreground hover:text-foreground cursor-pointer transition-colors ${showFilters ? "text-foreground" : ""}`}
          title="Toggle filters"
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
        </button>
      )}
      <ExpandCollapseButtons
        onExpandAll={() => setForceOpen((p) => ({ value: true, rev: (p?.rev ?? 0) + 1 }))}
        onCollapseAll={() => setForceOpen((p) => ({ value: false, rev: (p?.rev ?? 0) + 1 }))}
      />
      <button
        onClick={handleClearAll}
        className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
      >
        Load another
      </button>
    </span>
  </div>
  {showFilters && session.messages.length > 0 && (
    <div className="px-5 py-1.5 border-t border-border">
      <FeedFilters
        messages={session.messages}
        filters={filters}
        bookmarkCount={0}
        onChange={setFilters}
      />
    </div>
  )}
</header>
```

- [ ] **Step 3: Update content padding**

Replace:

```tsx
<div className="p-4">
```

With:

```tsx
<div className="px-5 py-4">
```

- [ ] **Step 4: Remove unused imports**

Remove `FolderOpen` from lucide-react. Remove `Button` from `@/components/ui/button` if no longer used in this file.

- [ ] **Step 5: Verify in browser**

Run `BUILD_STATIC=1 pnpm run dev`. Load a session. Header should match the live viewer — single line, no blur, toggleable filters.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past-viewer/src/entries/static.tsx
git commit -m "style(viewer): static entry single-line header"
```

---

### Task 15: Cleanup — verify query-result and remove unused components

**Files:**
- Verify: `packages/linked-past-viewer/src/components/query-result.tsx`
- Check: `packages/linked-past-viewer/src/components/ui/card.tsx`

**Note:** The spec lists `query-result.tsx` in "Files to Modify" with "Ensure no wrapping container." It already uses a bare `<div>` wrapper — no change needed. Verify this is still the case.

- [ ] **Step 1: Check for remaining Card imports**

Run from the viewer package root:

```bash
grep -r "from.*ui/card" src/ --include="*.tsx" --include="*.ts"
```

If no files import from `ui/card.tsx`, the component is unused.

- [ ] **Step 2: Check for remaining Badge imports in xref-list context**

```bash
grep -r "from.*ui/badge" src/ --include="*.tsx" --include="*.ts"
```

If Badge is only used by xref-list (which we changed in Task 10), verify it was removed.

- [ ] **Step 3: Keep or note unused files**

Per the spec: "May become unused — keep for now, remove if no imports remain." If Card has zero imports, delete `src/components/ui/card.tsx`. If Badge has zero imports, delete `src/components/ui/badge.tsx`. If they still have imports from other components not in this plan, keep them.

- [ ] **Step 4: Commit if any files removed**

```bash
git add -A packages/linked-past-viewer/src/components/ui/
git commit -m "chore(viewer): remove unused Card and Badge components"
```

---

### Task 16: Final visual review

- [ ] **Step 1: Test live viewer**

Run `pnpm run dev` with the MCP server. Open http://localhost:5173/viewer/. Run a few queries. Verify:
- Header: single line, no blur, bottom rule
- Feed items: divider lines, no boxes
- Entity content: flush, no card wrapper
- Data tables: typographic headers, no hover
- Dataset labels: colored text, no pills
- Entity URIs: plain links, underline on hover, popovers work
- Filters: toggle via icon, minimal chips

- [ ] **Step 2: Test static viewer**

Run `BUILD_STATIC=1 pnpm run dev`. Open http://localhost:5173/linked-past/viewer/. Load a file. Verify the same visual changes apply.

- [ ] **Step 3: Test static build**

```bash
pnpm run build:static
```

Verify build completes without errors.

- [ ] **Step 4: Test live build**

```bash
pnpm run build
```

Verify build completes without errors.

- [ ] **Step 5: Commit any final tweaks**

If any visual inconsistencies were found and fixed during review, commit them:

```bash
git add -A packages/linked-past-viewer/src/
git commit -m "style(viewer): final visual polish for Swiss redesign"
```
