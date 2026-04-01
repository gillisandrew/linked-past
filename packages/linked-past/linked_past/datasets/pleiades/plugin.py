"""Pleiades dataset plugin."""

from __future__ import annotations

from linked_past.datasets.base import DatasetPlugin


class PleiadesPlugin(DatasetPlugin):
    name = "pleiades"
    display_name = "Pleiades Gazetteer of Ancient Places"
    description = (
        "A community-built gazetteer and graph of ancient places, "
        "covering the Greek and Roman world with ~41,000 places, "
        "locations, and historical names."
    )
    citation = (
        "Pleiades: A Gazetteer of Past Places, "
        "https://pleiades.stoa.org"
    )
    license = "CC BY 3.0"
    url = "https://pleiades.stoa.org"
    time_coverage = "Archaic period through Late Antiquity"
    spatial_coverage = "Greek and Roman world"
    oci_dataset = "datasets/pleiades"
    oci_version = "latest"
