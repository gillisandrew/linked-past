"""Nomisma dataset plugin."""

from __future__ import annotations

from linked_past.datasets.base import DatasetPlugin


class NomismaPlugin(DatasetPlugin):
    name = "nomisma"
    display_name = "Nomisma.org Numismatic Vocabulary"
    description = (
        "A collaborative project providing stable digital representations "
        "of numismatic concepts — people, mints, denominations, materials, "
        "and regions — as Linked Open Data."
    )
    citation = (
        "Nomisma.org, http://nomisma.org"
    )
    license = "CC BY"
    url = "http://nomisma.org"
    time_coverage = "Ancient through modern numismatics"
    spatial_coverage = "Global"
    oci_dataset = "datasets/nomisma"
    oci_version = "latest"
