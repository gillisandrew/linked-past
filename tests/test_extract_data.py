"""Tests for scripts/extract_data.py using SAMPLE_TURTLE from test_store.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add scripts/ to the path so we can import extract_data
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_data import (  # noqa: E402
    build_search_index,
    extract_offices,
    extract_persons,
    slugify,
    strip_label_prefix,
    to_bool,
    to_int,
)
from pyoxigraph import RdfFormat, Store

from tests.test_store import SAMPLE_TURTLE

# We need to add extra test data for richer coverage
EXTENDED_TURTLE = (
    SAMPLE_TURTLE
    + """
<http://romanrepublic.ac.uk/rdf/entity/Person/1>
    vocab:hasPraenomen <http://romanrepublic.ac.uk/rdf/entity/Praenomen/L> ;
    vocab:hasFiliation "M. f." ;
    vocab:hasHighestOffice "cos. 509" ;
    vocab:isPatrician "true"^^xsd:boolean ;
    vocab:hasEraFrom "-509"^^xsd:integer ;
    vocab:hasEraTo "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Praenomen/L> a vocab:Praenomen ;
    rdfs:label "Praenomen: L." ;
    vocab:hasName "Lucius" .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1>
    vocab:hasSecondarySource <http://romanrepublic.ac.uk/rdf/entity/SecondarySource/1> .

<http://romanrepublic.ac.uk/rdf/entity/SecondarySource/1> a vocab:SecondarySource ;
    rdfs:label "Secondary Source: Broughton MRR I" ;
    vocab:hasName "Broughton MRR I" .

<http://romanrepublic.ac.uk/rdf/entity/RelationshipAssertion/1> a vocab:RelationshipAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasRelatedPerson <http://romanrepublic.ac.uk/rdf/entity/Person/2> ;
    vocab:hasRelationship <http://romanrepublic.ac.uk/rdf/entity/Relationship/colleague_of> .

<http://romanrepublic.ac.uk/rdf/entity/Relationship/colleague_of> a vocab:Relationship ;
    rdfs:label "Relationship: colleague of" .

<http://romanrepublic.ac.uk/rdf/entity/StatusAssertion/1> a vocab:StatusAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasStatus <http://romanrepublic.ac.uk/rdf/entity/Status/senator> ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Status/senator> a vocab:Status ;
    rdfs:label "Status: senator" .

<http://romanrepublic.ac.uk/rdf/entity/DateInformation/1> a vocab:DateInformation ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasDateType <http://romanrepublic.ac.uk/rdf/entity/DateType/death> ;
    vocab:hasValue "-509"^^xsd:integer ;
    vocab:hasDateInterval "S" .

<http://romanrepublic.ac.uk/rdf/entity/DateType/death> a vocab:DateType ;
    rdfs:label "Date Type: death" .

<http://romanrepublic.ac.uk/rdf/entity/TribeAssertion/1> a vocab:TribeAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasTribe <http://romanrepublic.ac.uk/rdf/entity/Tribe/Cornelia> .

<http://romanrepublic.ac.uk/rdf/entity/Tribe/Cornelia> a vocab:Tribe ;
    rdfs:label "Tribe: Cornelia" .

<http://romanrepublic.ac.uk/rdf/entity/PersonNote/1> a vocab:PersonNote ;
    vocab:hasNoteText "A founding figure of the Republic." .

<http://romanrepublic.ac.uk/rdf/entity/Person/1>
    vocab:hasPersonNote <http://romanrepublic.ac.uk/rdf/entity/PersonNote/1> .
"""
)


def _make_store(turtle: str = EXTENDED_TURTLE) -> Store:
    """Create an ephemeral store loaded with test data."""
    store = Store()
    with tempfile.NamedTemporaryFile(suffix=".ttl", mode="w", delete=False) as f:
        f.write(turtle)
        f.flush()
        store.bulk_load(path=f.name, format=RdfFormat.TURTLE)
    return store


def _prefix_map() -> dict[str, str]:
    """Minimal prefix map for tests."""
    return {
        "vocab": "http://romanrepublic.ac.uk/rdf/ontology#",
        "entity": "http://romanrepublic.ac.uk/rdf/entity/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
    }


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self):
        assert slugify("consul") == "consul"

    def test_spaces(self):
        assert slugify("consul suffectus") == "consul-suffectus"

    def test_uppercase(self):
        assert slugify("Broughton MRR I") == "broughton-mrr-i"

    def test_extra_spaces(self):
        assert slugify("  tribunus  plebis  ") == "tribunus-plebis"


class TestStripLabelPrefix:
    def test_office(self):
        assert strip_label_prefix("Office: consul") == "consul"

    def test_sex(self):
        assert strip_label_prefix("Sex: Male") == "Male"

    def test_no_prefix(self):
        assert strip_label_prefix("just a string") == "just a string"

    def test_none(self):
        assert strip_label_prefix(None) is None


class TestToBool:
    def test_true(self):
        assert to_bool("true") is True

    def test_false_string(self):
        assert to_bool("false") is False

    def test_none(self):
        assert to_bool(None) is False


class TestToInt:
    def test_positive(self):
        assert to_int("42") == 42

    def test_negative(self):
        assert to_int("-509") == -509

    def test_none(self):
        assert to_int(None) is None

    def test_invalid(self):
        assert to_int("abc") is None


# ---------------------------------------------------------------------------
# Integration tests with SAMPLE_TURTLE
# ---------------------------------------------------------------------------


class TestExtractPersons:
    def test_returns_two_persons(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        assert len(persons) == 2

    def test_person_fields(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert brutus["nomen"] == "Iunius"
        assert brutus["cognomen"] == "Brutus"
        assert brutus["praenomen"] == "Lucius"
        assert brutus["filiation"] == "M. f."
        assert brutus["eraFrom"] == -509
        assert brutus["eraTo"] == -509
        assert brutus["sex"] == "Male"
        assert brutus["patrician"] is True
        assert brutus["highestOffice"] == "cos. 509"

    def test_person_name_strips_dprr_id(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")
        assert brutus["name"] == "L. Iunius Brutus"
        assert "IUNI0001" not in brutus["name"]

    def test_post_assertions(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert len(brutus["postAssertions"]) >= 1
        pa = brutus["postAssertions"][0]
        assert pa["office"] == "consul"
        assert pa["officeId"] == "consul"
        assert pa["dateStart"] == -509
        assert pa["dateEnd"] == -509
        assert len(pa["sources"]) >= 1
        assert pa["sources"][0]["name"] == "Broughton MRR I"
        assert pa["sources"][0]["id"] == "broughton-mrr-i"

    def test_relationships(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert len(brutus["relationships"]) == 1
        rel = brutus["relationships"][0]
        assert rel["type"] == "colleague of"
        assert rel["relatedPersonId"] == "TARQ0001"

    def test_status_assertions(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert len(brutus["statusAssertions"]) >= 1
        sa = brutus["statusAssertions"][0]
        assert sa["status"] == "senator"
        assert sa["dateStart"] == -509

    def test_date_information(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert len(brutus["dateInformation"]) == 1
        di = brutus["dateInformation"][0]
        assert di["type"] == "death"
        assert di["value"] == -509
        assert di["interval"] == "S"

    def test_tribe_assertions(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert len(brutus["tribeAssertions"]) == 1
        ta = brutus["tribeAssertions"][0]
        assert ta["tribe"] == "Cornelia"

    def test_person_notes(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        brutus = next(p for p in persons if p["id"] == "IUNI0001")

        assert "A founding figure of the Republic." in brutus["notes"]

    def test_person_without_optional_fields(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        tarq = next(p for p in persons if p["id"] == "TARQ0001")

        # TARQ0001 has no praenomen entity, no filiation, no era, no flags
        assert tarq["praenomen"] is None
        assert tarq["filiation"] is None
        assert tarq["patrician"] is False
        assert tarq["relationships"] == []
        assert tarq["statusAssertions"] == []
        assert tarq["dateInformation"] == []
        assert tarq["tribeAssertions"] == []


class TestExtractOffices:
    def test_returns_offices(self):
        store = _make_store()
        offices = extract_offices(store, _prefix_map())
        assert len(offices) >= 1

    def test_office_fields(self):
        store = _make_store()
        offices = extract_offices(store, _prefix_map())
        consul = next(o for o in offices if o["id"] == "consul")

        assert consul["name"] == "consul"
        assert consul["holders"] is not None
        assert len(consul["holders"]) == 2  # both persons hold consul

    def test_office_holders_have_person_data(self):
        store = _make_store()
        offices = extract_offices(store, _prefix_map())
        consul = next(o for o in offices if o["id"] == "consul")

        person_ids = {h["personId"] for h in consul["holders"]}
        assert "IUNI0001" in person_ids
        assert "TARQ0001" in person_ids

    def test_office_name_from_label_fallback(self):
        """Office without vocab:hasName should fall back to rdfs:label."""
        store = _make_store(SAMPLE_TURTLE)  # original data has no vocab:hasName on Office
        offices = extract_offices(store, _prefix_map())
        assert len(offices) >= 1
        consul = offices[0]
        assert consul["name"] == "consul"


class TestBuildSearchIndex:
    def test_includes_persons_and_offices(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        offices = extract_offices(store, _prefix_map())
        index = build_search_index(persons, offices)

        types = {item["type"] for item in index}
        assert "person" in types
        assert "office" in types

    def test_person_entry_shape(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        offices = extract_offices(store, _prefix_map())
        index = build_search_index(persons, offices)

        person_entry = next(i for i in index if i["type"] == "person" and i["id"] == "IUNI0001")
        assert person_entry["name"] == "L. Iunius Brutus"
        assert person_entry["nomen"] == "Iunius"
        assert person_entry["era"] == "-509 to -509"

    def test_office_entry_shape(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        offices = extract_offices(store, _prefix_map())
        index = build_search_index(persons, offices)

        office_entry = next(i for i in index if i["type"] == "office")
        assert "name" in office_entry
        assert "id" in office_entry

    def test_total_count(self):
        store = _make_store()
        persons = extract_persons(store, _prefix_map())
        offices = extract_offices(store, _prefix_map())
        index = build_search_index(persons, offices)
        assert len(index) == len(persons) + len(offices)
