"""CRRO dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class CRROPlugin(DatasetPlugin):
    name = "crro"
    display_name = "Coinage of the Roman Republic Online (CRRO)"
    description = (
        "A digital type corpus of 2,602 Roman Republican coin types based on "
        "Crawford's Roman Republican Coinage (RRC). Each type documents denomination, "
        "issuing authority, mint, material, and obverse/reverse iconography with "
        "links to Nomisma concepts."
    )
    citation = (
        "American Numismatic Society, Coinage of the Roman Republic Online, "
        "https://numismatics.org/crro/. Based on Crawford, M.H. (1974) "
        "Roman Republican Coinage."
    )
    license = "ODbL 1.0"
    url = "https://numismatics.org/crro"
    time_coverage = "c. 280-27 BC"
    spatial_coverage = "Roman Republic"
    oci_dataset = "datasets/crro"
    oci_version = "latest"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://numismatics.org/crro/nomisma.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
