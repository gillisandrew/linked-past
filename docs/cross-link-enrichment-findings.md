# Cross-Link Enrichment Findings

Notes from the DPRR cross-dataset linkage enrichment session (2026-03-30).

## 1. The URI Mismatch Bug

The original 5 DPRR→Pleiades province links used **slug-based URIs** (`Province/Sicilia`) that didn't match the **numeric URIs** in the DPRR Oxigraph store (`Province/5`). This meant `find_links("Province/5")` returned nothing — the curated links were effectively invisible to any query starting from SPARQL results.

The fix was straightforward (switch to numeric URIs), but the bug illustrates a common Linked Data pitfall: linkage graphs and dataset stores can silently disagree on URI forms, and the mismatch only surfaces when you try to traverse the link from one system to the other.

## 2. The Aquillius Family and the Smyrna Milestone (HD051507)

While investigating the praetors of 132 BC, we followed M'. Aquillius (cos. 129 BC) through his family relationships in DPRR and searched for cross-references in EDH. This led to **inscription HD051507**, a bilingual Latin/Greek milestone found near Smyrna in the province of Asia.

The inscription reads:

> *[M. Aq]uillius M. f. cos.* — Manius Aquillius, son of Manius, consul
> *L. Aquillius M. f. M. n. Florus q. restituit* — Lucius Aquillius Florus, quaestor, restored [this milestone]

This single stone connects three generations:
- **M'. Aquillius (cos. 101 BC)** — DPRR Person/1757 — the consul who built the road during his proconsulship of Asia (128–126 BC)
- **Aquillius Florus (q. c. 70 BC)** — DPRR Person/4686 — the grandson who restored it as quaestor, with filiation "M. f. M. n." (son of Manius, grandson of Manius) matching DPRR's genealogy exactly

The milestone is an epigraphic attestation of a DPRR family relationship across three generations, with the grandson literally maintaining the physical legacy of his grandfather's provincial command. None of these connections existed in the linkage graph before this session.

## 3. The Plautius/Plotius Orthographic Variant

Semantic embedding search (BAAI/bge-small-en-v1.5 cosine similarity) caught a match that name-based matching missed: EDH person "A. Plotius (= Plautius)" matching DPRR's "A. Plautius (Plotius)."

The alternation between *Plautius* and *Plotius* is a known phenomenon in Republican-era Latin orthography — the AU/O vowel shift. DPRR records both forms (the nomen field is "Plautius (Plotius)"), but the EDH record uses only the Plotius form. Standard nomen matching fails because "Plautius" ≠ "Plotius" at the string level.

This is a proof of concept for embedding-based matching of orthographic variants. The yield was small (the Plautius/Plotius case is well-known enough that DPRR already annotates it), but the technique could find less-documented variants.

## 4. Greek Transliteration Unlocks Eastern Inscriptions

Adding a Greek→Latin transliteration pipeline to the EDH matching script produced **13 new confirmed links** from bilingual inscriptions in the eastern provinces. Key mappings:

- **κ → c**: Κ. Ἀνχάριος → C. Ancharius (the systematic Greek use of kappa for Latin C)
- **ου → u**: Αὐτρώνιος → Autronius (Greek diphthong for Latin long U)
- **-ιος → -ius**: Standard Greek→Latin name ending conversion

These matches involve persons with **rare nomina** (Ancharius, Insteius, Marcilius, Cottius, Autronius, Magius, Pupius) — exactly the cases where a unique gens name makes identification confident even without cognomen or date overlap.

The transliteration handles the systematic phonetic correspondences. It cannot handle irregular Hellenizations where the Greek form diverges from predictable transliteration rules.

## 5. The Gens Ambiguity Wall

The single largest barrier to automated cross-dataset person matching is **gens ambiguity**: the great Roman families had dozens of members sharing identical praenomen + nomen + cognomen across centuries.

Scale of the problem from our EDH matching:
- **18** DPRR persons named P. Cornelius Scipio match a single EDH inscription
- **16** M. Claudii Marcelli for one EDH entry
- **14** Q. Fabii Maximi

These cannot be resolved by:
- **Date overlap**: DPRR era ranges are broad (50–100 year spans) and multiple family members' eras overlap
- **EDH inscription dates**: Mostly absent for the matched persons (49,294 of 70,215 inscriptions are dated, but the elite persons on those inscriptions often lack individual date annotations)
- **Semantic embeddings**: The descriptions are too similar (all are "senator, held consulship, served in province X")
- **Name components**: Praenomen, nomen, and cognomen all match — there are no distinguishing name elements

What *could* help:
- **Filiation matching**: Some EDH entries include "M. f." (son of Marcus), "Cn. n." (grandson of Gnaeus), which narrows candidates within a gens
- **Province/geography matching**: If DPRR records a proconsulship in Asia and the inscription was found in Asia, that's corroborating evidence
- **Inscription content analysis**: The actual text of the inscription sometimes mentions offices held, which could be cross-referenced against DPRR career data

These all require more sophisticated matching than string comparison — they need prosopographic reasoning about career sequences and family trees.

## 6. Summary Statistics

| Linkage | Before | After | Method |
|---------|--------|-------|--------|
| DPRR → Pleiades (provinces) | 5 | 68 | Manual curation via MCP tools |
| DPRR → Nomisma (moneyers) | 187 | 266 | Automated name+date matching |
| DPRR → EDH (persons) | 0 | 34 | Name matching + Greek transliteration + manual |
| DPRR → PeriodO (periods) | 2 | 9 | Manual curation |
| DPRR → OCRE | 0 | 0 | No overlap (OCRE is post-Republic) |
| **Total** | **194** | **377** | **+183 new links** |

Scripts produced: `match_dprr_nomisma.py`, `disambiguate_nomisma.py`, `match_dprr_edh.py`, `disambiguate_edh.py`, `semantic_match_edh.py`.
