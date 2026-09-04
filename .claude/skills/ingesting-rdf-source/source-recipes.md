# Source Recipes

Each recipe names the script that already does this. Read that script before
writing a new one.

## RDF/XML at a URL (CRRO, OCRE, RPC)

`scripts/ingest_generic.py` with `source_format: rdf-xml`. It injects a
DOCTYPE declaring `&nbsp;` so files using HTML entities parse, converts with
`rapper`, and pushes. Known gaps handled elsewhere: placeholder IRIs (`-`,
`—`), trailing whitespace in IRIs, interior spaces (see
`docs/data-lifecycle.md`, "IRI-level issues"). If a new RDF/XML source hits
one of those, extend the generic script's rewrite step rather than adding a
bespoke script.

## JSON-LD at a URL (PeriodO)

`scripts/ingest_generic.py` with `source_format: json-ld`, or
`scripts/ingest_periodo.py` when the download needs a custom step. Conversion
is `rdflib.Graph().parse(format="json-ld")` then `serialize(format="turtle")`.
JSON-LD contexts fetched over the network can fail silently; verify the
triple count is in the expected range.

## Turtle in a release tarball (DPRR)

`scripts/ingest_dprr.py`: download the tarball, extract the single `.ttl`,
push. Pattern: `tarfile.open(...).extractall(tmpdir)` then locate the file
by suffix rather than by a hardcoded name.

## Many Turtle files in a git checkout (Pleiades)

`scripts/ingest_pleiades.py` and `.github/workflows/ingest-pleiades.yml`:
sparse-checkout the upstream repo, concatenate the files in sorted order with
a `# Source:` comment before each, apply source-specific IRI repairs
(`%23` to `#`, missing `place-types/` segment, truncated subresource
references via `scripts/fix_pleiades_refs.py`), push. Concatenation is safe
because each file declares its own prefixes.

## Local zip that cannot be downloaded (EDH)

`scripts/ingest_edh.py`: reads `edh_linked_data.zip` from the repo root
(gitignored, obtained by hand), extracts all Turtle files, pushes them as a
multi-layer artifact. The plugin's default `load` handles multi-file
datasets by loading every non-underscore `.ttl` in the dataset directory.

## SPARQL endpoint (DPRR before the release tarball existed)

`scripts/extract_from_endpoint.py`: page through `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT n OFFSET m`
until a page returns fewer than `n` triples, append each page to one file.
The DPRR endpoint sits behind a proof-of-work bot shield; the script prompts
for a browser session cookie when direct requests fail. Expect endpoints to
cap result sizes; keep the page size at or below the cap.

## N3 export with the wrong namespace (DPRR)

`scripts/convert_n3_to_ttl.py` parses N3 with rdflib and re-serializes as
Turtle; `scripts/rebind_prefixes.py` rebinds prefixes to the documented
namespaces. Namespace choice matters because the plugin's `prefixes.yaml`
and every example depend on it.

## RDF/XML with Unicode replacement characters in IRIs (Nomisma)

`scripts/ingest_nomisma.py`: after conversion, corrects two known DBpedia
IRIs where Turkish characters were lost upstream, and strips any remaining
lines containing U+FFFD. A replacement character in an IRI is unrecoverable
in general; correct known cases, drop the rest, and print the count.
