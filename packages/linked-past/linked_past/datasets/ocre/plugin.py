"""OCRE dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class OCREPlugin(DatasetPlugin):
    name = "ocre"
    display_name = "Online Coins of the Roman Empire (OCRE)"
    description = (
        "A digital type corpus of ~50,000 Roman Imperial coin types from "
        "RIC (Roman Imperial Coinage). Each type documents denomination, "
        "issuing emperor, mint, material, and obverse/reverse iconography "
        "with links to Nomisma concepts."
    )
    citation = (
        "American Numismatic Society, Online Coins of the Roman Empire, "
        "https://numismatics.org/ocre/. Based on Mattingly, H. et al., "
        "Roman Imperial Coinage (RIC)."
    )
    license = "ODbL 1.0"
    url = "https://numismatics.org/ocre"
    time_coverage = "c. 31 BC - 491 AD"
    spatial_coverage = "Roman Empire"
    oci_dataset = "datasets/ocre"
    oci_version = "latest"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://numismatics.org/ocre/nomisma.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
