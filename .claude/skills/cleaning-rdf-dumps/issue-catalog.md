# Issue Catalog by Symptom

The canonical catalog is the "Catalog of upstream data issues" section of
`docs/data-lifecycle.md`. This file indexes it by what you see in the parser
error, and says where the fix already lives.

## The XML parser fails

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| `undefined entity` naming `nbsp`, `mdash`, `ndash` | HTML entities in RDF/XML text | `scripts/ingest_generic.py` DOCTYPE injection |
| HTTP 403 on download | Host blocks default Python user agent | `scripts/ingest_generic.py` sends `User-Agent: linked-past/1.0` |

## The IRI is rejected

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| Invalid IRI `-` or `—` | Placeholder values in `rdf:resource` | Ingest rewrite: drop the attribute |
| IRI ending in a space | Trailing whitespace upstream | Ingest rewrite: strip |
| IRI with an interior space | Unencoded local names | Ingest rewrite: percent-encode to `%20` |
| IRI containing U+FFFD | Characters lost upstream | `scripts/ingest_nomisma.py`: correct known cases, drop the rest |
| `<doi.org/10....>` rejected | Bare DOI without scheme | `linked_past_store/sanitize.py` `_BARE_DOI` |

## The Turtle parser rejects a line

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| Error on a literal with `@` followed by a long tag | BCP 47 subtag over 8 characters (`@etruscan-in-latin-characters`) | `sanitize.py` `_LANG_TAG` and `_fix_lang_tag`: known tags map to private-use forms like `@x-etruscan-latn`; unknown tags drop oversized subtags |
| Parses, but subjects like `.../433134%23this` never match `#this` | Percent-encoded fragment | `scripts/ingest_pleiades.py` and workflow: `%23` to `#` |
| Parses, but `/vocabularies/abbey` has no definition | Missing path segment | `scripts/ingest_pleiades.py`: insert `place-types/` |

## It parses but the data is wrong

| You see | Cause | Fix lives in |
|---------|-------|--------------|
| `hasLocation` / `hasName` objects have no triples | Truncated subresource references (`/places/<slug>` instead of `/places/<id>/<slug>`) | `scripts/fix_pleiades_refs.py` at ingest |
| Duplicate labels, one tagged `@en` and one untagged | Language tags dropped during materialization | `linked_past/core/store.py` `materialize` preserves `Literal.language` and `.datatype` |
| Predicate under `http://lawd.info/ontology/1.0/` does not match `lawd:` prefix | Upstream uses a versioned namespace | `prefixes.yaml` plus a tip explaining the versioned IRI (EDH) |
| Diagnostic lines like `rapper: Parsing ...` inside the Turtle | rapper wrote to stdout | `sanitize.py` `_RAPPER_LOG` strip |

## Deciding where a new fix goes

```
Would the same regex be correct on every other dataset?   yes -> sanitize.py
Is it about the source's serialization or packaging?      yes -> ingest script
Is it a namespace or ontology mismatch?                   yes -> prefixes.yaml / schemas.yaml + a tip
Is it an inference artifact?                              yes -> store.materialize
```
