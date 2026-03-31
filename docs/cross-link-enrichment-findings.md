# Cross-Link Enrichment Findings

Notes from the DPRR cross-dataset linkage enrichment session (2026-03-30).

## 1. The URI Mismatch Bug

The original 5 DPRR→Pleiades province links used **slug-based URIs** (`Province/Sicilia`) that didn't match the **numeric URIs** in the DPRR Oxigraph store (`Province/5`). This meant `find_links("Province/5")` returned nothing — the curated links were effectively invisible to any query starting from SPARQL results.

The fix was straightforward (switch to numeric URIs), but the bug illustrates a common Linked Data pitfall: linkage graphs and dataset stores can silently disagree on URI forms, and the mismatch only surfaces when you try to traverse the link from one system to the other.

## 2. The Aquillius Family and the Smyrna Milestone (CIL I² 647 / EDH HD051507)

While investigating the praetors of 132 BC, we followed M'. Aquillius (cos. 129 BC) through his family relationships in DPRR and searched for cross-references in EDH. This led to **CIL I² 647** (= EDH HD051507), a bilingual Latin/Greek milestone found near Smyrna in the province of Asia.

The inscription reads:

> *[M'. Aq]uillius M'. f. cos.* — Manius Aquillius, son of Manius, consul
> *L. Aquillius M'. f. M'. n. Florus q. restituit* — Lucius Aquillius Florus, quaestor, restored [this milestone]

This single stone connects three generations:
- **M'. Aquillius (cos. 129 BC)** — the consul who built the road during his proconsulship of Asia (129–126 BC), after suppressing the revolt of Aristonicus
- **M'. Aquillius (cos. 101 BC)** — DPRR Person/1757 — the son, who later served in Asia in the 90s BC and was killed by Mithridates
- **L. Aquillius Florus (q. c. 70 BC)** — DPRR Person/4686 — the grandson who restored it as quaestor, with filiation "M'. f. M'. n." (son of Manius, grandson of Manius) matching DPRR's genealogy exactly

The "restituit" act is not merely road maintenance — scholars read it as a **public assertion of hereditary patronage** (*clientela*) over the province. The filiation formula makes the dynastic claim unmistakable to any traveler on the road.

**Scholarly context:**
- The milestone is part of the road network Aquillius established from Ephesus to Pergamum and onward (French, RRMAM 3.1). David French noted scholarly debate about whether Aquillius paved new roads or merely marked existing Hellenistic routes with Roman milestones.
- The Aquillius family's multigenerational connection to Asia is paralleled by other Republican families (Mucii Scaevolae, Metelli) but the milestone is unusual in providing physical, epigraphic evidence on a single monument.
- **David French, *Roman Roads and Milestones of Asia Minor* 3.1** (BIAA, open access at biaa.ac.uk) is the definitive modern corpus for these milestones.
- **Magie, *Roman Rule in Asia Minor* (1950)** for the provincial context.
- **Broughton, *Magistrates of the Roman Republic*** for both Aquillii's careers.
- **Petzl, *Die Inschriften von Smyrna* (IK Smyrna, 1982–1990)** for the inscription corpus.

## 3. The Plautius/Plotius Orthographic Variant

Semantic embedding search (BAAI/bge-small-en-v1.5 cosine similarity) caught a match that name-based matching missed: EDH person "A. Plotius (= Plautius)" matching DPRR's "A. Plautius (Plotius)."

The alternation between *Plautius* and *Plotius* is a well-attested phenomenon of Republican Latin — the **monophthongization of AU → O**, where /au/ reduces to /oː/ in certain sociolinguistic registers. The same shift produces Claudius/Clodius, *cauda*/*coda*, *plaustrum*/*plostrum*.

**The scholarly consensus** (Allen, *Vox Latina* 1978, pp. 60–64; Leumann, *Lateinische Laut- und Formenlehre* 1977, §§79–80) is that AU and O forms **coexisted as sociolinguistic variants**, not as a simple chronological development: AU was the prestige/conservative form, O was popular/rustic. In names, the choice could be politically charged — P. Clodius Pulcher's adoption of the O-form is the most famous case (Tatum, *The Patrician Tribune*, 1999).

**For the gens Plautia/Plotia specifically:** Münzer (RE XXI.1, 1951) notes the O-form is predominant in earlier Republican usage, with AU-forms becoming standard in later literary texts. The family was of plebeian origin, probably from around Tibur. Syme ("Clodius or Claudius?", *Historia* 7, 1958) argues that modern editors should respect source forms rather than silently normalizing.

**Implications for digital prosopography:**
- String matching alone will miss phonological variants. **Solin & Salomies, *Repertorium Nominum Gentilium* (1994)** is the standard reference for mapping variant forms and should serve as a variant gazetteer for any matching pipeline.
- The **SNAP:DRGN project** (snap.drgn.net) addresses this by using URIs for person identification rather than relying on name-string matching.
- Computational approaches (e.g., **CLTK** — Classical Language Toolkit) have begun to address fuzzy name-matching for phonological variants, but this is still early-stage for prosopographic use.

## 4. Greek Transliteration Unlocks Eastern Inscriptions

Adding a Greek→Latin transliteration pipeline to the EDH matching script produced **13 new confirmed links** from bilingual inscriptions in the eastern provinces. Key mappings:

- **κ → c**: Κ. Ἀνχάριος → C. Ancharius (the systematic Greek use of kappa for Latin C)
- **ου → u**: Αὐτρώνιος → Autronius (Greek diphthong for Latin long U)
- **-ιος → -ius**: Standard Greek→Latin name ending conversion
- **Consonantal V → Ου**: Valerius → Οὐαλέριος (one of the most distinctive features)

These matches involve persons with **rare nomina** (Ancharius, Insteius, Marcilius, Cottius, Autronius, Magius, Pupius) — exactly the cases where a unique gens name makes identification confident even without cognomen or date overlap.

**Scholarly context:**
- The standard reference for Greek renderings of Roman praenomina is **Salomies, *Die römischen Vornamen* (1987)**.
- **Mason, *Greek Terms for Roman Institutions* (1974)** covers the broader transliteration conventions.
- **Adams, *Bilingualism and the Latin Language* (2003)** treats Greek-Latin bilingualism in the eastern provinces, including onomastic practices.
- **Hatzfeld, *Les trafiquants italiens dans l'Orient hellénique* (1919)** is the classic study of Italian names in Greek inscriptions, especially from Delos.
- The chronological shift from **Λεύκιος** (Republican) to **Λούκιος** (Imperial) for Lucius is a potential dating signal for future disambiguation.

**No one has published a dedicated Greek↔Latin prosopographic matching tool.** Our pipeline (rule-based transliteration → nomen matching against DPRR) appears to be a novel contribution. The closest existing system is **Trismegistos People** (KU Leuven), which does semi-automated cross-script matching. **LGPN** (Lexicon of Greek Personal Names, Oxford) is the natural partner database for Greek-attested Roman names.

## 5. The Gens Ambiguity Wall

The single largest barrier to automated cross-dataset person matching is **gens ambiguity**: the great Roman families had dozens of members sharing identical praenomen + nomen + cognomen across centuries.

Scale of the problem from our EDH matching:
- **18** DPRR persons named P. Cornelius Scipio match a single EDH inscription
- **16** M. Claudii Marcelli for one EDH entry
- **14** Q. Fabii Maximi

These cannot be resolved by automated name/date matching because DPRR era ranges are broad, EDH inscription dates are mostly absent for these persons, and the descriptions are too similar for semantic differentiation.

**What the scholarship suggests could help:**
- **Filiation matching**: "M. f. Cn. n." encodes two generations of ancestry and is the single most powerful disambiguator (Verboven & Carlier, "A Short Manual to the Art of Prosopography").
- **Cursus honorum constraints**: The fixed progression of Roman magistracies with legally mandated minimum ages and intervals constrains which offices a given individual could have held. **No computational system has yet formalized these constraints for disambiguation**, despite their power.
- **Berkeley Prosopography Services (BPS)** (Pearce & Schmitz, *ISAW Papers* 7, 2014) is the most developed computational disambiguation engine — built for Neo-Babylonian tablets, with a plug-in rule architecture adaptable to Roman tria nomina. Uses heuristic rules on filiation, social network, and temporal constraints.
- **Romans 1by1** (DHQ 18.2, 2024) experiments with graph database modeling for prosopographic disambiguation of ~18k persons from Moesian/Dacian inscriptions.
- **DPRR's factoid prosopography model** (Bradley, "A Prosopography as Linked Open Data", *Digital Humanities Quarterly* 14.2, 2020) was developed at KCL and provides the LOD infrastructure. DPRR IDs are registered as **Wikidata property P6863**.

**The key gap:** No automated system combining career-sequence constraints + filiation matching + graph-based network analysis exists for Roman prosopography. This would be the highest-impact computational contribution to the field.

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

## 7. Key References

### Prosopography & Methodology
- Bradley, J. "A Prosopography as Linked Open Data." *DHQ* 14.2 (2020).
- Broughton, T.R.S. *The Magistrates of the Roman Republic*. 3 vols. APA, 1951–1986.
- Münzer, F. *Roman Aristocratic Parties and Families*. Johns Hopkins, 1999 (trans. Ridley).
- Pearce, L. and Schmitz, P. "Berkeley Prosopography Services." *ISAW Papers* 7 (2014).
- Verboven, K. and Carlier, M. "A Short Manual to the Art of Prosopography."

### Latin Phonology & Onomastics
- Allen, W.S. *Vox Latina*. 2nd ed. Cambridge, 1978.
- Kajanto, I. *The Latin Cognomina*. Helsinki, 1965.
- Salomies, O. *Die römischen Vornamen*. Helsinki, 1987.
- Solin, H. and Salomies, O. *Repertorium Nominum Gentilium et Cognominum Latinorum*. 2nd ed. Hildesheim, 1994.

### Epigraphy & Bilingualism
- Adams, J.N. *Bilingualism and the Latin Language*. Cambridge, 2003.
- French, D. *Roman Roads and Milestones of Asia Minor* 3.1. BIAA (open access).
- Hatzfeld, J. *Les trafiquants italiens dans l'Orient hellénique*. Paris, 1919.
- Magie, D. *Roman Rule in Asia Minor*. 2 vols. Princeton, 1950.
- Mason, H.J. *Greek Terms for Roman Institutions*. Toronto, 1974.
- Sherk, R.K. *Roman Documents from the Greek East*. Baltimore, 1969.

### Digital Infrastructure
- DPRR: romanrepublic.ac.uk (Wikidata property P6863)
- SNAP:DRGN: snapdrgn.net
- Trismegistos People: trismegistos.org/ref
- LGPN: lgpn.classics.ox.ac.uk
- BPS: berkeleyprosopography.org
