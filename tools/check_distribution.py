"""Run under an isolated wheel installation, without the editable package."""
import json
import sqlite3
from contextlib import closing
import tempfile
from importlib.metadata import version
import subprocess
import sys
from pathlib import Path
import bioevidence_validator
from bioevidence_validator.engine import default_schema_path, default_policy_path, validate_record

root = Path(__file__).resolve().parents[1]
assert root / "src" not in Path(bioevidence_validator.__file__).resolve().parents
assert version("bioai-evidence-validator") == bioevidence_validator.__version__ == "0.3.0"
assert default_schema_path().is_file() and default_policy_path().is_file()
for filename, expected in [("valid_labrador.json", 0), ("ambiguous_boxer.json", 1)]:
    source = root / "examples/canine_breed" / filename
    result = subprocess.run([sys.executable, "-m", "bioevidence_validator.cli", "validate", str(source)],
                            capture_output=True, text=True, encoding="utf-8", cwd=root.parent)
    assert result.returncode == expected, result.stderr
    report = json.loads(result.stdout)
    assert report["overall_status"] == ("admitted" if expected == 0 else "rejected")
    assert len(report["policy_sha256"]) == 64
record = json.loads((root / "examples/canine_breed/valid_labrador.json").read_text(encoding="utf-8"))
record["requested_uses"] = []
assert validate_record(record)["overall_status"] == "rejected"
print("Installed-wheel resources, CLI acceptance/rejection, and invalid-input guard verified.")

# Exercise the read-only adapter from the installed distribution, including its
# strict manifest parser and the packaged 0.3 policy/schema imports.
with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    database = tmp / "synthetic.sqlite"
    with closing(sqlite3.connect(database)) as db, db:
        db.executescript("""
        CREATE TABLE source_records(record_key TEXT,source TEXT,source_raw_labels TEXT,
          source_concept_id TEXT,source_name_status TEXT,candidate_concept_ids TEXT);
        CREATE TABLE concepts(source_concept_id TEXT,source_name TEXT);
        CREATE VIEW resolved_source_names AS SELECT record_key,source_concept_id FROM source_records;
        INSERT INTO source_records VALUES('synthetic:1','Synthetic','Labrador','VBO:LAB','UNIQUE','VBO:LAB');
        INSERT INTO concepts VALUES('VBO:LAB','Labrador');
        """)
    manifest = tmp / "manifest.yaml"
    manifest.write_text('database_title: Synthetic\ndatabase_version: "1"\nretrieved_at: "2026-09-21T00:00:00Z"\nontology_version: synthetic\nconcept_status_default: current\nbreed_scope_default: breed\nrequested_uses_default: [display_name]\n', encoding="utf-8")
    output = tmp / "output"
    result = subprocess.run([sys.executable, "-m", "bioevidence_validator.cli", "export-canine-panel",
                             str(database), "--manifest", str(manifest), "--output", str(output)],
                            capture_output=True, text=True, encoding="utf-8", cwd=tmp)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete" and summary["exported_records"] == 1
    assert summary["validation_statuses"] == {"admitted": 1}
    assert not Path(str(database) + "-wal").exists()
print("Installed-wheel SQLite adapter, strict manifest and batch completion verified.")
