"""Exercise the installed wheel from outside editable source on both CI platforms."""
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import bioevidence_validator
from bioevidence_validator.engine import default_schema_path, profile_path, validate_record

root = Path(__file__).resolve().parents[1]
package = Path(bioevidence_validator.__file__).resolve().parent
assert root / "src" not in package.parents
assert version("bioai-evidence-validator") == bioevidence_validator.__version__ == "0.6.0"
assert default_schema_path().is_file()
assert all(profile_path(name).is_file() for name in ("general", "literature-claim", "dataset-label"))
assert not (package / "canine_panel_adapter.py").exists()
assert not list(package.rglob("*canine*"))


def run(*args, expected=0):
    result = subprocess.run([sys.executable, "-m", "bioevidence_validator.cli", *map(str, args)],
                            capture_output=True, text=True, encoding="utf-8", cwd=root.parent)
    assert result.returncode == expected, (result.stdout, result.stderr)
    return result


for path, profile, expected in [
    ("general/curated_assertion.json", "general", 0),
    ("literature_claim/curated_association.json", "literature-claim", 0),
    ("literature_claim/llm_only.json", "literature-claim", 2),
    ("dataset_label/curated_sample_label.json", "dataset-label", 0),
    ("dataset_label/missing_sample_link.json", "dataset-label", 1),
    ("custom_profile/assay_record.json", root / "examples/custom_profile/assay.yaml", 0),
]:
    result = run("validate", root / "examples" / path, "--profile", profile, expected=expected)
    report = json.loads(result.stdout)
    assert report["overall_status"] == {0: "admitted", 1: "rejected", 2: "review_required"}[expected]
    assert len(report["profile_sha256"]) == len(report["input_sha256"]) == 64
assert len(json.loads(run("profiles").stdout)) == 3
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "schema.json"
    run("generate-schema", "--output", output)
    assert "BioEvidenceRecord" in json.loads(output.read_text(encoding="utf-8"))["$defs"]
with tempfile.TemporaryDirectory() as directory:
    for draft, profile, expected in [
        ("llm_claim.yaml", "literature-claim", 2),
        ("reviewed_claim.yaml", "literature-claim", 0),
        ("dataset_label_reference.yaml", "dataset-label", 0),
        ("dataset_label_training_unreviewed.yaml", "dataset-label", 1),
    ]:
        output = Path(directory) / (draft + ".json")
        run("build", root / "examples/drafts" / draft, "--output", output)
        run("validate", output, "--profile", profile, expected=expected)
    schema = json.loads(run("draft-schema", "--profile", "literature-claim").stdout)
    assert schema["properties"]["profile"] == {"const": "literature-claim"}
record = json.loads((root / "examples/general/curated_assertion.json").read_text(encoding="utf-8"))
record["requested_uses"] = []
assert validate_record(record)["overall_status"] == "rejected"
print("Installed wheel: generic schema, all profiles, custom domain, drafts, CLI outcomes and admission guard verified.")

# The example imports the installed generic core; it is kept outside the wheel.
with tempfile.TemporaryDirectory() as directory:
    result = subprocess.run([sys.executable, str(root / "examples/vbo_canine/run.py"),
                             "--output", str(Path(directory) / "vbo")],
                            capture_output=True, text=True, encoding="utf-8", cwd=root.parent)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["cohorts"]["controlled_fault"]["full"]["false_admissions"] == 0
    assert summary["cohorts"]["trust_boundary"]["full"]["false_admissions"] == 16
print("Installed wheel: real-source VBO case, required-type quality fix and explicit trust boundary verified.")

with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "clinvar"
    result = subprocess.run([sys.executable, str(root / "examples/clinvar_germline/run.py"), "--output", str(output)],
                            capture_output=True, text=True, encoding="utf-8", cwd=root.parent)
    assert result.returncode == 0, result.stderr
    for expected in (root / "examples/clinvar_germline/results").iterdir():
        assert expected.read_bytes() == (output / expected.name).read_bytes(), expected.name
print("Installed wheel: ClinVar case replays its committed results byte-for-byte.")
