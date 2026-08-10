"""Fix truncated subresource references in the Pleiades RDF dump.

Upstream bug (pleiades.datasets RDF export): place records reference their
location and name subresources as /places/<slug> instead of
/places/<id>/<slug> — the exporter resolves the relative slug against a base
URI without a trailing slash, so RFC 3986 resolution replaces the place id
instead of appending. The subresources themselves are correctly defined at
/places/<id>/<slug> in the same files, so every hasLocation/hasName reference
dangles (67K+ in the 2025 dump). The same applies to the /errata/ scheme.

The missing id is recoverable from the referencing subject, so this rewrites
each truncated object to <subject-uri>/<slug>. Line-based: the dump serializes
one predicate group per line, with multi-object lists continued on
indented lines containing only <uri>, / <uri>; / <uri> . tokens.

Usage (prints the number of rewritten references):
    python -m scripts.fix_pleiades_refs <file.ttl>
"""

import re
import sys

_SUBJECT = re.compile(r"^<https://pleiades\.stoa\.org/(places|errata)/(\d+)>")
_REF_PRED = re.compile(r"pleiades:has(?:Location|Name)\b")
_CONTINUATION = re.compile(r"^\s*<[^>]+>\s*[,;.]?\s*$")


def _truncated_ref(scheme: str) -> re.Pattern:
    # A direct child of /places/ or /errata/ whose slug starts with a
    # non-digit: numeric ids are real top-level resources, slugs are not.
    # No '/', '#', or ':' in the slug — full subresource URIs and vocabulary
    # pages never match.
    return re.compile(rf"<https://pleiades\.stoa\.org/{scheme}/([^\d/>#:][^/>#:]*)>")


def fix_truncated_refs(text: str) -> tuple[str, int]:
    """Rewrite truncated hasLocation/hasName references. Returns (text, count)."""
    out_lines = []
    count = 0
    subject: tuple[str, str] | None = None  # (scheme, id)
    in_ref_pred = False

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        starts_at_col0 = line and not line[0].isspace()

        if starts_at_col0:
            m = _SUBJECT.match(line)
            subject = (m.group(1), m.group(2)) if m else None
            # The subject line may carry its first predicate group.
            in_ref_pred = bool(_REF_PRED.search(line))
        elif _CONTINUATION.match(line):
            pass  # object list continuation — keep predicate state
        elif stripped:
            in_ref_pred = bool(_REF_PRED.match(stripped))
        else:
            subject = None
            in_ref_pred = False

        if subject and in_ref_pred:
            scheme, sid = subject
            line, n = _truncated_ref(scheme).subn(
                rf"<https://pleiades.stoa.org/{scheme}/{sid}/\1>", line
            )
            count += n

        out_lines.append(line)

    return "".join(out_lines), count


def main(path: str) -> None:
    with open(path) as f:
        text = f.read()
    fixed, count = fix_truncated_refs(text)
    if count:
        with open(path, "w") as f:
            f.write(fixed)
    print(count)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.fix_pleiades_refs <file.ttl>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
