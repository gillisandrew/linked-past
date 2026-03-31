"""Download Nomisma concept vocabulary, sanitize, and push to OCI registry.

The upstream Nomisma Turtle has syntax issues:
- Parentheses in local names: nm:foo(bar) → nm:foo%28bar%29
- Empty local names: nm: ; → removed
- Other invalid characters in local names

We fix these by regex-replacing known patterns, then verify with pyoxigraph.
"""

import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "http://nomisma.org/nomisma.org.ttl"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/nomisma"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://nomisma.org",
    "org.opencontainers.image.description": (
        "Nomisma.org numismatic concept vocabulary (sanitized for Oxigraph)"
    ),
    "org.opencontainers.image.licenses": "CC-BY-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Nomisma.org / American Numismatic Society",
    "dev.linked-past.dataset": "nomisma",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Gruber, E. & Meadows, A. (2021). ISAW Papers 20.6",
}


def _percent_encode_local_name(match: re.Match) -> str:
    """Percent-encode invalid characters in a prefixed local name."""
    prefix = match.group(1)
    local = match.group(2)
    # Percent-encode parentheses and other invalid chars
    local = local.replace("(", "%28").replace(")", "%29")
    return f"{prefix}:{local}"


def _sanitize_turtle(raw_text: str) -> tuple[str, int]:
    """Fix known syntax issues in Nomisma Turtle. Returns (fixed_text, fix_count)."""
    fixes = 0

    # Fix 1: Percent-encode parentheses in nm: local names
    # Match nm:something(something) patterns
    pattern = re.compile(r'\b(nm):([a-zA-Z_][^\s;,.\]]*\([^\s;,.]*\))')
    raw_text, n = pattern.subn(_percent_encode_local_name, raw_text)
    fixes += n

    # Fix 2: Remove lines with empty local name (nm: followed by whitespace + ; or .)
    # These are dangling references like "dcterms:isReplacedBy nm: ;"
    empty_ref = re.compile(r'^\s+\S+\s+nm:\s*[;.]\s*$', re.MULTILINE)
    raw_text, n = empty_ref.subn('', raw_text)
    fixes += n

    return raw_text, fixes


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        raw_path = tmpdir / "nomisma_raw.ttl"
        urllib.request.urlretrieve(SOURCE_URL, str(raw_path))
        print(f"Downloaded {raw_path} ({raw_path.stat().st_size:,} bytes)")

        raw_text = raw_path.read_text(errors="replace")
        print("Sanitizing Turtle (fixing invalid local names)...")
        fixed_text, fix_count = _sanitize_turtle(raw_text)
        print(f"Applied {fix_count} regex fixes")

        # Write fixed text, then do block-by-block verification as fallback
        # for any remaining issues (invalid Unicode, etc.)
        from pyoxigraph import RdfFormat, Store

        # Extract prefix block
        prefix_lines = []
        for line in fixed_text.split("\n"):
            if line.strip().startswith("@prefix") or line.strip().startswith("PREFIX"):
                prefix_lines.append(line)
            elif prefix_lines and line.strip() == "":
                continue
            elif prefix_lines:
                break
        prefix_block = "\n".join(prefix_lines) + "\n"

        remainder = fixed_text[fixed_text.index(prefix_lines[-1]) + len(prefix_lines[-1]):]
        blocks = remainder.split("\n\n")

        clean_path = tmpdir / "nomisma.ttl"
        kept = 0
        dropped = 0
        with open(clean_path, "w") as out:
            out.write(prefix_block + "\n")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                chunk = prefix_block + "\n" + block
                try:
                    s = Store()
                    s.load(chunk.encode("utf-8", errors="replace"), RdfFormat.TURTLE)
                    if len(s) > 0:
                        out.write(block + "\n\n")
                        kept += 1
                    del s
                except Exception:
                    dropped += 1

        print(f"Kept {kept:,} blocks, dropped {dropped:,}")

        # Final verification
        print("Final verification...")
        store = Store()
        store.bulk_load(path=str(clean_path), format=RdfFormat.TURTLE)
        print(f"Verified: {len(store):,} triples")
        del store

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "nomisma.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
