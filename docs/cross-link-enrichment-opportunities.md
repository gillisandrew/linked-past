# Cross-Link Enrichment Opportunities for DPRR

Assessed 2026-03-30 against linked-past datasets.

## Current State

| Linkage | Links | Coverage |
|---------|-------|----------|
| DPRR → Nomisma (confirmed) | ~187 person links | Moneyers matched to Nomisma person authorities |
| DPRR → Nomisma (probable) | 6 links | Uncertain matches needing review |
| DPRR → Pleiades | 5 province links | 5 of 92 provinces (Sicilia, Africa, Hispania, Asia, Gallia) |
| DPRR → PeriodO | 2 era links | Republic + Late Republic |
| Wikidata-derived | Nomisma↔Pleiades, Pleiades↔TM | Place concordances (indirect to DPRR) |

## Opportunities

### 1. DPRR Provinces → Pleiades (IN PROGRESS)

Only 5 of ~50 geographic provinces are linked. ~45 real geographic provinces (Macedonia, Syria, Sardinia, Cilicia, Aegyptus, Bithynia, etc.) have obvious Pleiades counterparts. ~20 of the 92 "provinces" are legal categories (repetundae, ambitus, urbanus) that wouldn't link.

**Effort:** Low — straightforward geographic matching.

### 2. DPRR Persons → CRRO Coin Types (via issuers)

CRRO has 454 distinct issuers from Nomisma. The confirmed linkage covers ~187 DPRR persons → Nomisma. DPRR records 293 monetales + 79 moneyers = ~370 persons with coin-minting offices. Many CRRO issuers remain unlinked.

**Opportunity:** Match ~180+ remaining CRRO issuers to DPRR persons by cross-referencing names and dates.
**Effort:** Medium — requires name normalization (CRRO uses abbreviated Latin forms like `l_piso_frvgi_rrc`).

### 3. DPRR Persons → EDH Inscriptions

EDH has 87,329 persons from 70,215 inscriptions, including 4,702 of senatorial order and 1,624 equestrians. DPRR has 4,876 persons (overwhelmingly senators and equites). Zero DPRR↔EDH links exist today.

**Opportunity:** Match senatorial-order EDH persons to DPRR persons by nomen + date overlap. Conservative approach (consuls, famous senators) could yield hundreds of links.
**Effort:** High — requires fuzzy name matching, date range overlap, manual verification.

### 4. DPRR → OCRE Transitional Figures

OCRE covers 31 BC onward (imperial coinage). DPRR ends at 31 BC. Overlap for ~10-20 transitional figures (Augustus/Octavian, Antony, Lepidus).

**Effort:** Low — small number of well-known figures.

### 5. PeriodO Sub-Period Granularity

Only 2 PeriodO links exist. PeriodO has definitions for Early Republic, Middle Republic, Social War era, etc.

**Effort:** Low but lower impact.

## Recommended Priority

1. DPRR Provinces → Pleiades — fast win, unlocks spatial bridging to EDH
2. DPRR → CRRO/Nomisma expansion — builds on existing infrastructure
3. DPRR → EDH persons — highest scholarly value, start with consuls
4. DPRR → OCRE transitional figures — small, easy
5. PeriodO sub-periods — nice-to-have
