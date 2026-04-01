"""EDH (Epigraphic Database Heidelberg) dataset plugin."""

from __future__ import annotations

from linked_past.datasets.base import DatasetPlugin


class EDHPlugin(DatasetPlugin):
    name = "edh"
    display_name = "Epigraphic Database Heidelberg (EDH)"
    description = (
        "81,000+ Latin inscriptions from across the Roman Empire with transcriptions, "
        "findspots, dates, and prosopographic data. Includes diplomatic and scholarly "
        "edition texts."
    )
    citation = (
        "Epigraphic Database Heidelberg, https://edh.ub.uni-heidelberg.de/. "
        "CC BY-SA 4.0."
    )
    license = "CC BY-SA 4.0"
    url = "https://edh.ub.uni-heidelberg.de"
    time_coverage = "Antiquity through Late Antiquity"
    spatial_coverage = "Roman Empire"
    oci_dataset = "datasets/edh"
    oci_version = "latest"
