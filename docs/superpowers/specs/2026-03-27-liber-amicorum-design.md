# Liber Amicorum — Design Spec

A prerendered, searchable web directory of Roman Republican figures and offices, built from the DPRR RDF dataset.

## Audience

Primary: scholars and researchers wanting quick reference cards with full source citations and uncertainty flags. Secondary: students and the general public browsing a "who's who" of the Roman Republic. Start scholar-focused; the static, linkable nature makes it naturally accessible to a broader audience over time.

## Repository Structure

Simple top-level monorepo split — no workspace tooling. Python MCP server and TypeScript site have separate toolchains.

```
dprr-tool/
├── dprr_mcp/                # Python MCP server (unchanged)
├── liber-amicorum/           # TanStack Start app
│   ├── src/
│   │   ├── routes/           # file-based routes
│   │   ├── components/       # React components
│   │   │   └── ui/           # shadcn/ui components
│   │   └── data/             # TS modules that import extracted JSON
│   ├── components.json       # shadcn/ui config
│   ├── vite.config.ts
│   ├── wrangler.jsonc
│   └── package.json
├── scripts/
│   ├── extract_data.py       # SPARQL → JSON extraction
│   ├── convert_n3_to_ttl.py
│   ├── extract_from_endpoint.py
│   └── rebind_prefixes.py
├── data/
│   ├── dprr.ttl              # source RDF
│   └── extracted/            # pipeline output
│       ├── persons.json
│       ├── offices.json
│       └── search-index.json
├── tests/
├── pyproject.toml
└── CLAUDE.md
```

## Data Pipeline

A Python script (`scripts/extract_data.py`) loads `data/dprr.ttl` (committed to the repo) into an ephemeral pyoxigraph store, runs SPARQL queries, and writes JSON to `data/extracted/`.

The MCP server is not involved — the extraction script reuses pyoxigraph directly. This keeps the site build independent of any running service. In CI, `dprr.ttl` is available from the repo checkout — no download step needed.

### ID Conventions

- **Person IDs** use the DPRR ID directly (e.g., `IUNI0001`), which is already URL-safe.
- **Office IDs** are URL-safe slugs derived from `vocab:hasName` by lowercasing and replacing spaces with hyphens (e.g., `"consul suffectus"` → `"consul-suffectus"`). The extraction script generates these deterministically.

### JSON Contract

**persons.json** — array of person objects:

```json
[
  {
    "id": "IUNI0001",
    "name": "L. Iunius M. f. Brutus",
    "praenomen": "Lucius",
    "nomen": "Iunius",
    "cognomen": "Brutus",
    "filiation": "M. f.",
    "eraFrom": -509,
    "eraTo": -509,
    "sex": "Male",
    "patrician": false,
    "nobilis": true,
    "novus": false,
    "highestOffice": "cos. 509",
    "reNumber": "46a",
    "origin": null,
    "praenomenUncertain": false,
    "nomenUncertain": false,
    "cognomenUncertain": false,
    "filiationUncertain": false,
    "otherNamesUncertain": false,
    "patricianUncertain": false,
    "notes": ["..."],
    "postAssertions": [
      {
        "office": "consul",
        "officeId": "consul",
        "dateStart": -509,
        "dateEnd": -509,
        "province": "Latium",
        "provinceUncertain": false,
        "uncertain": false,
        "dateStartUncertain": false,
        "dateEndUncertain": false,
        "sources": [
          { "name": "Broughton MRR I", "id": "broughton-mrr-i" }
        ],
        "dateSource": { "name": "Broughton MRR I", "id": "broughton-mrr-i" },
        "notes": [],
        "originalText": null
      }
    ],
    "relationships": [
      {
        "type": "father of",
        "relatedPersonId": "IUNI0002",
        "relatedPersonName": "Ti. Iunius Brutus"
      }
    ],
    "statusAssertions": [
      {
        "status": "senator",
        "dateStart": -509,
        "dateEnd": -509,
        "uncertain": false,
        "dateStartUncertain": false,
        "dateEndUncertain": false,
        "sources": [{ "name": "Broughton MRR I", "id": "broughton-mrr-i" }],
        "notes": [],
        "originalText": null
      }
    ],
    "dateInformation": [
      {
        "type": "death - violent",
        "value": -509,
        "interval": "S",
        "uncertain": false,
        "source": { "name": "Broughton MRR I", "id": "broughton-mrr-i" }
      }
    ],
    "tribeAssertions": []
  }
]
```

**offices.json** — array of office objects:

```json
[
  {
    "id": "consul",
    "name": "consul",
    "abbreviation": "cos.",
    "parentId": null,
    "parentName": null,
    "children": [
      { "id": "consul-suffectus", "name": "consul suffectus" }
    ],
    "holders": [
      {
        "personId": "IUNI0001",
        "personName": "L. Iunius M. f. Brutus",
        "dateStart": -509,
        "dateEnd": -509,
        "uncertain": false,
        "dateStartUncertain": false,
        "dateEndUncertain": false,
        "sources": [
          { "name": "Broughton MRR I", "id": "broughton-mrr-i" }
        ]
      }
    ]
  }
]
```

**search-index.json** — flat array of searchable documents:

```json
[
  {
    "id": "IUNI0001",
    "type": "person",
    "name": "L. Iunius M. f. Brutus",
    "nomen": "Iunius",
    "cognomen": "Brutus",
    "praenomen": "Lucius",
    "highestOffice": "cos. 509",
    "era": "-509 to -509"
  },
  {
    "id": "consul",
    "type": "office",
    "name": "consul",
    "abbreviation": "cos."
  }
]
```

### Relationship Depth

Each person's `relationships` array contains direct (first-degree) relationships only. Every related person is identified by `relatedPersonId`, making them a link to their own page. Users navigate the full relationship network by clicking through — the graph doesn't need to be flattened into each record.

### Uncertainty as First-Class Data

Every assertion (post, status, tribe, date) carries uncertainty flags at the assertion level and on individual fields (dates, province). The extraction script preserves all of these. The UI surfaces them prominently — scholars should see at a glance what's contested.

## Routes & Page Types

```
liber-amicorum/src/routes/
├── __root.tsx              # layout: nav, search bar, footer
├── index.tsx               # homepage: project intro, featured figures, browse links
├── explore/
│   └── index.tsx           # full-featured data exploration table
├── persons/
│   ├── index.tsx           # person listing: alphabetical by nomen, filterable
│   └── $personId.tsx       # individual person page
├── offices/
│   ├── index.tsx           # office listing: grouped by hierarchy
│   └── $officeId.tsx       # individual office page
└── 404.tsx                 # not found
```

### Explore Page (`/explore`)

A full-featured data exploration table powered by TanStack Table, giving researchers direct access to the entire dataset:

- **All persons in a single table** with columns: name, nomen, cognomen, praenomen, era, sex, highest office, patrician, nobilis, novus, origin
- **Column sorting** — click any header to sort (e.g., sort by era to find earliest/latest figures)
- **Column filtering** — per-column filters: text search on name fields, range filters on dates, dropdown/facet filters on sex, patrician, nobilis, etc.
- **Column visibility** — toggle columns on/off to focus on what matters
- **Pagination** — client-side, with configurable page size
- **Row links** — each row links to the full person page
- Uncertainty markers shown inline where applicable

This is the power-user view. The listing pages (`/persons`, `/offices`) remain as simpler, more browsable entry points.

### Person Page (`/persons/IUNI0001`)

- **Header:** full name (with per-component uncertainty markers on praenomen, nomen, cognomen, filiation), era, sex, patrician/nobilis/novus badges with uncertainty markers
- **Post Assertions table** (TanStack Table): office (linked), dates, province, secondary sources, notes — sortable by date/office, uncertainty flagged inline. Sources shown per-assertion, not collapsed.
- **Status Assertions** (TanStack Table): senator/eques with dates, sources, uncertainty — sortable
- **Date Information:** birth, death, floruit etc. with sources
- **Relationships:** direct relationships as linked cards showing name, type, and era
- **Notes:** person notes at bottom

### Office Page (`/offices/consul`)

- **Header:** office name, abbreviation, parent office (linked)
- **Holders table** (TanStack Table): person (linked), dates, province, sources — sortable by date/name, filterable. Uncertainty flagged inline.
- **Child offices:** listed and linked if any

### Listing Pages

- **Persons index:** alphabetical by nomen, showing era range and highest office. MiniSearch bar at top for filtering. All person links rendered in the initial HTML (no client-side pagination) — required for `crawlLinks` prerender discovery.
- **Offices index:** grouped by office hierarchy (magistracies, priesthoods, military, etc.), with holder counts. All office links rendered in initial HTML.

## Search

**Build-time:** Python extraction script writes `search-index.json`.

**Client-side MiniSearch:**
- Loaded lazily on first search interaction
- Indexed fields: `name`, `nomen`, `cognomen`, `praenomen` for persons; `name`, `abbreviation` for offices
- Boosted fields: `nomen` and `cognomen` weighted higher (scholars search by family name)
- Fuzzy matching enabled for Latin spelling variations
- Results grouped by type (persons / offices), each linking to its page

**Search UI:**
- Persistent search bar in the root layout header
- Dropdown results as-you-type (debounced ~150ms)
- Keyboard navigable (arrow keys + enter)
- On listing pages, the same MiniSearch drives inline filtering

## Prerender & Deployment

### Vite Config

```ts
// vite.config.ts
import { defineConfig } from "vite-plus"
import { tanstackStart } from "@tanstack/react-start/plugin/vite"
import { cloudflare } from "@cloudflare/vite-plugin"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  resolve: { tsconfigPaths: true },
  plugins: [
    cloudflare({ viteEnvironment: { name: "ssr" } }),
    tanstackStart({
      prerender: {
        enabled: true,
        crawlLinks: true,
        pages: [{ path: "/" }, { path: "/404" }],
      },
    }),
    react(),
    tailwindcss(),
  ],
})
```

The crawler starts from `/` → discovers listing pages → follows all entity links → prerenders every person and office page. If scale becomes an issue, switch to the explicit `prerender-paths.json` pattern (as in endo).

### Cloudflare Workers

Deployed as a Cloudflare Worker (not Pages), matching endo and agillis.dev. `wrangler.jsonc` with `server.ts` entry point. Prerendered pages served as static assets; the Worker handles 404s, redirects, and any future dynamic needs.

### CI Pipeline (GitHub Actions)

1. Install Python deps: `uv sync`
2. Run extraction: `uv run python scripts/extract_data.py`
3. Install JS deps: `cd liber-amicorum && vp install`
4. Build site: `cd liber-amicorum && vp build`
5. Deploy: `wrangler deploy`

### SEO

TanStack Start auto-generates `sitemap.xml` when prerender + crawlLinks are enabled. Each entity page gets a `<title>` and `<meta description>` from extracted data.

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | TanStack Start (React) | File-based routing, SSR/prerender |
| Build | Vite+ (`vp`) | `defineConfig` from `vite-plus` |
| Styling | Tailwind CSS v4 | `@tailwindcss/vite` plugin |
| UI Components | shadcn/ui | Radix primitives + Tailwind, classic aesthetic |
| Data Tables | TanStack Table | Sorting, filtering, column visibility, pagination |
| Search | MiniSearch | Build-time index, client-side fuzzy search |
| Data pipeline | Python (pyoxigraph) | SPARQL → JSON extraction script |
| Hosting | Cloudflare Workers | `@cloudflare/vite-plugin` + wrangler |
| Prerender | TanStack Start built-in | `crawlLinks: true` from listing pages |
| Package manager | pnpm | Matching existing projects |
| Monorepo | Simple top-level split | No workspace tooling |

## Design Direction

Stately, classic aesthetic befitting a scholarly prosopography:

- **Typography:** Serif or transitional typeface for headings (e.g., Literata, Source Serif). Clean sans-serif for body/tables.
- **Whitespace:** Generous — let the data breathe.
- **Palette:** Muted, warm tones. Parchment-inspired backgrounds, deep blue/green accents. No bright SaaS colors.
- **Tables:** Styled after academic reference works — clear rules, compact but readable.
- **Uncertainty markers:** Subtle but unmistakable — italic text with dotted underlines, not loud warning colors. Tooltips with source detail.

## Initial Scope

**Included:** Persons, Offices, PostAssertions, Relationships (on person pages), StatusAssertions, DateInformation, TribeAssertions (on person pages), SecondarySource citations.

**Deferred:** Dedicated pages for tribes, provinces, secondary sources, primary sources, relationship types. These entity types appear as data on person/office pages but don't get their own route in v1.

## Not Included (Intentionally)

- No i18n — Latin names don't need translation
- No map/geographic visualization
- No Storybook — lean start
- No runtime MCP server dependency — site is fully static at build time
