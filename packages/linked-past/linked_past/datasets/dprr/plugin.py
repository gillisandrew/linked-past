"""DPRR dataset plugin."""

from __future__ import annotations

import os
from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo

_DEFAULT_DATA_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


class DPRRPlugin(DatasetPlugin):
    name = "dprr"
    display_name = "Digital Prosopography of the Roman Republic"
    description = (
        "A structured prosopography of the political elite of the Roman Republic "
        "(c. 509-31 BC), documenting persons, office-holdings, family relationships, "
        "and social status with full source citations."
    )
    citation = (
        "Sherwin et al., Digital Prosopography of the Roman Republic, "
        "romanrepublic.ac.uk"
    )
    license = "CC BY-NC 4.0"
    url = "https://romanrepublic.ac.uk"
    time_coverage = "509-31 BC"
    spatial_coverage = "Roman Republic"
    oci_dataset = "datasets/dprr"
    oci_version = "latest"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        url = os.environ.get("DPRR_DATA_URL", _DEFAULT_DATA_URL)
        return VersionInfo(
            version=self.oci_version,
            source_url=url,
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
