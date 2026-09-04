"""Kerameikos.org dataset plugin."""

from __future__ import annotations

from pathlib import Path

from linked_past.datasets.base import DatasetPlugin, VersionInfo


class KerameikosPlugin(DatasetPlugin):
    name = "kerameikos"
    display_name = "Kerameikos.org: Linked Open Greek Pottery"
    description = (
        "Concept vocabulary for ancient Greek pottery: about 460 SKOS concepts covering "
        "230 painters and potters, 40 painter groups and classes, 127 vessel shapes, "
        "22 techniques, styles, materials, production places, and periods. Labels in "
        "over 100 languages; concordances to Wikidata, Getty AAT/ULAN/TGN, the British "
        "Museum, VIAF, and Pleiades. Modelled with SKOS, CIDOC-CRM, and the ORG ontology."
    )
    citation = (
        "Gruber, Ethan and Smith, Tyler Jo, Kerameikos.org: Linked Open Greek Pottery, "
        "https://kerameikos.org/. American Numismatic Society and University of Virginia. "
        "ODbL 1.0."
    )
    license = "ODbL 1.0"
    url = "https://kerameikos.org"
    time_coverage = "c. 900-300 BC (Geometric to Classical Greece)"
    spatial_coverage = "Greek world, chiefly Attica, Corinth, and South Italy"
    oci_dataset = "datasets/kerameikos"
    oci_version = "latest"

    def get_version_info(self, data_dir: Path) -> VersionInfo:
        return VersionInfo(
            version=self.oci_version,
            source_url="https://kerameikos.org/kerameikos.org.rdf",
            fetched_at="",
            triple_count=0,
            rdf_format="turtle",
        )
