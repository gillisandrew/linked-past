"""RPC dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class RPCPlugin(DatasetPlugin):
    name = "rpc"
    display_name = "Roman Provincial Coinage Online (RPC)"
    description = (
        "A standard typology of coins minted in the provinces of the Roman "
        "Empire (44 BC – 296 AD). Each type documents denomination, issuing "
        "authority, mint, material, and obverse/reverse iconography with "
        "links to Nomisma concepts."
    )
    citation = (
        "Burnett, A., Amandry, M., and Ripollès, P.P., Roman Provincial "
        "Coinage, https://rpc.ashmus.ox.ac.uk/. University of Oxford."
    )
    license = "ODbL 1.0"
    url = "https://rpc.ashmus.ox.ac.uk"
    time_coverage = "44 BC – 296 AD"
    spatial_coverage = "Roman provinces"
    oci_dataset = "datasets/rpc"
    oci_version = "latest"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://rpc.ashmus.ox.ac.uk/rpc/nomisma.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
