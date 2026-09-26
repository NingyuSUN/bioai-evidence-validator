"""Keep the machine-readable ECO meanings, the documentation and the compiled schema consistent."""
import json
import re
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

from bioevidence_validator.engine import (
    default_schema_path,
    generate_json_schema,
    validate_record,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"deterministic_parser": "ECO:0000313", "manual_curation": "ECO:0000352",
            "normalized_string_match": "ECO:0008021", "llm_extraction": "ECO:0008004"}


def meanings():
    view = SchemaView(str(default_schema_path()))
    return view, {name: value.meaning for name, value in view.get_enum("ExtractionMethod").permissible_values.items()}


def test_every_extraction_method_has_the_documented_eco_meaning():
    view, found = meanings()
    assert found == EXPECTED
    for curie in found.values():
        assert view.expand_curie(curie) == "http://purl.obolibrary.org/obo/ECO_" + curie.split(":")[1]


def test_standards_doc_matches_the_schema():
    doc = (ROOT / "docs/STANDARDS.md").read_text(encoding="utf-8")
    for method, curie in EXPECTED.items():
        assert re.search(rf"^\| `{method}` \| `{curie}` ", doc, re.MULTILINE), method


def test_annotations_do_not_change_validation():
    compiled = generate_json_schema()["$defs"]["ExtractionMethod"]
    assert compiled == {"description": "", "enum": list(EXPECTED), "title": "ExtractionMethod", "type": "string"}


def test_eco_report_annotations_are_opt_in_and_schema_derived():
    record = json.loads(
        (ROOT / "examples/general/curated_assertion.json").read_text(encoding="utf-8")
    )
    base = record["evidence_items"][0]
    record["evidence_items"] = [
        {**base, "id": f"bioev:{method}", "extraction_method": method}
        for method in EXPECTED
    ]
    record["statement"]["evidence_lines"][0]["evidence_item_ids"] = [
        "bioev:manual_curation"
    ]

    plain = validate_record(record)
    annotated = validate_record(record, annotate_eco=True)

    assert "evidence_eco_annotations" not in plain
    assert annotated["evidence_eco_annotations"] == [
        {
            "evidence_item_id": f"bioev:{method}",
            "extraction_method": method,
            "eco_curie": curie,
        }
        for method, curie in EXPECTED.items()
    ]
