"""PeriodO dataset plugin."""

from __future__ import annotations

from linked_past.datasets.base import DatasetPlugin


class PeriodOPlugin(DatasetPlugin):
    name = "periodo"
    display_name = "PeriodO"
    description = (
        "A gazetteer of scholarly definitions of historical, art-historical, "
        "and archaeological periods. Each period has temporal bounds, spatial "
        "coverage, and provenance from a specific authority."
    )
    citation = (
        "PeriodO, A gazetteer of period definitions for linking "
        "and visualizing data, https://perio.do"
    )
    license = "CC0"
    url = "https://perio.do"
    time_coverage = "All periods (prehistoric through modern)"
    spatial_coverage = "Global"
    oci_dataset = "datasets/periodo"
    oci_version = "latest"
