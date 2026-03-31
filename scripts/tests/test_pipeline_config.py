"""Tests for pipeline_config module."""

import textwrap

import pytest
import yaml


@pytest.fixture
def sample_config(tmp_path):
    """Write a minimal datasets.yaml and return its path."""
    data = {
        "test_dataset": {
            "raw_ref": "ghcr.io/test/raw/test:latest",
            "clean_ref": "ghcr.io/test/datasets/test:latest",
            "ingest_script": "scripts/ingest_generic.py",
            "fetch_url": "https://example.org/data.rdf",
            "source_format": "rdf-xml",
            "min_triple_count": 1000,
            "license": "CC-BY-4.0",
            "source_url": "https://example.org",
            "description": "Test dataset",
            "citation": textwrap.dedent("""\
                @misc{test2024,
                  author = {Smith, John},
                  title  = {Test Dataset},
                  year   = {2024},
                  note   = {CC BY 4.0}
                }
            """),
        }
    }
    config_path = tmp_path / "datasets.yaml"
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return config_path


def test_load_config(sample_config):
    from scripts.pipeline_config import load_config

    config = load_config(sample_config)
    assert "test_dataset" in config
    assert config["test_dataset"]["license"] == "CC-BY-4.0"
    assert config["test_dataset"]["min_triple_count"] == 1000


def test_load_dataset_config(sample_config):
    from scripts.pipeline_config import load_dataset_config

    ds = load_dataset_config("test_dataset", sample_config)
    assert ds["raw_ref"] == "ghcr.io/test/raw/test:latest"
    assert ds["clean_ref"] == "ghcr.io/test/datasets/test:latest"


def test_load_dataset_config_unknown(sample_config):
    from scripts.pipeline_config import load_dataset_config

    with pytest.raises(KeyError, match="no_such_dataset"):
        load_dataset_config("no_such_dataset", sample_config)


def test_render_citation_to_text():
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{test2024,
          author = {Smith, John},
          title  = {Test Dataset},
          year   = {2024},
          note   = {CC BY 4.0}
        }
    """)
    text = render_citation(bibtex)
    assert "Smith" in text
    assert "Test Dataset" in text
    assert "2024" in text


def test_render_citation_double_braces():
    """BibTeX titles often use double braces for capitalization preservation."""
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{dprr,
          author = {Mouritsen, Henrik},
          title  = {{Digital Prosopography of the Roman Republic}},
          year   = {2017}
        }
    """)
    text = render_citation(bibtex)
    assert "Digital Prosopography" in text
    assert "Mouritsen" in text


def test_render_citation_empty():
    from scripts.pipeline_config import render_citation

    assert render_citation("") == ""


def test_render_citation_url_field():
    """Should fall back to url field if howpublished is absent."""
    from scripts.pipeline_config import render_citation

    bibtex = textwrap.dedent("""\
        @misc{test,
          author = {Smith, John},
          title  = {Test},
          year   = {2024},
          url    = {https://example.org}
        }
    """)
    text = render_citation(bibtex)
    assert "https://example.org" in text


def test_build_annotations(sample_config):
    from scripts.pipeline_config import build_annotations, load_dataset_config

    ds = load_dataset_config("test_dataset", sample_config)
    annotations = build_annotations(ds, "test_dataset")
    assert annotations["org.opencontainers.image.licenses"] == "CC-BY-4.0"
    assert annotations["org.opencontainers.image.source"] == "https://example.org"
    assert annotations["io.github.gillisandrew.linked-past.dataset"] == "test_dataset"
    assert "Smith" in annotations["io.github.gillisandrew.linked-past.citation"]
