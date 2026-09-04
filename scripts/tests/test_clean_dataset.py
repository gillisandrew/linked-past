"""Tests for the clean_dataset dry-run path."""

from pathlib import Path
from unittest.mock import patch

SAMPLE_TURTLE = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .
ex:Thing1 a ex:Widget ; rdfs:label "Widget One" .
ex:Thing2 a ex:Widget ; rdfs:label "Widget Two" .
"""


def test_no_push_writes_artifacts_locally_and_never_pushes(tmp_path):
    from scripts import clean_dataset

    raw_dir = tmp_path / "rawsrc"
    raw_dir.mkdir()
    raw_ttl = raw_dir / "dprr.ttl"
    raw_ttl.write_text(SAMPLE_TURTLE)
    out_dir = tmp_path / "out"

    def fake_pull(ref, dest):
        if "/raw/" in ref:
            return raw_ttl
        raise RuntimeError("no previous clean artifact")

    with (
        patch.object(clean_dataset, "pull_dataset", side_effect=fake_pull),
        patch.object(clean_dataset, "push_dataset") as push,
        patch.object(clean_dataset.ArtifactCache, "digest_for", return_value="sha256:test"),
    ):
        clean_dataset.main("dprr", push=False, out_dir=out_dir)

    push.assert_not_called()
    assert (out_dir / "dprr.ttl").read_text().count("ex:Widget") >= 1 or "Widget" in (out_dir / "dprr.ttl").read_text()
    assert (out_dir / "_void.ttl").exists()
    assert (out_dir / "_schema.yaml").exists()


def test_push_path_still_pushes(tmp_path):
    from scripts import clean_dataset

    raw_ttl = tmp_path / "dprr.ttl"
    raw_ttl.write_text(SAMPLE_TURTLE)

    def fake_pull(ref, dest):
        if "/raw/" in ref:
            return raw_ttl
        raise RuntimeError("no previous clean artifact")

    with (
        patch.object(clean_dataset, "pull_dataset", side_effect=fake_pull),
        patch.object(clean_dataset, "push_dataset", return_value="sha256:pushed") as push,
        patch.object(clean_dataset.ArtifactCache, "digest_for", return_value="sha256:test"),
    ):
        clean_dataset.main("dprr")

    push.assert_called_once()
    pushed_files = [Path(p).name for p in push.call_args.args[1]]
    assert pushed_files == ["dprr.ttl", "_void.ttl", "_schema.yaml"]
