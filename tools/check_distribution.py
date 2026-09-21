"""Run under an isolated wheel installation, without the editable package."""
import json
import subprocess
import sys
from pathlib import Path
import bioevidence_validator
from bioevidence_validator.engine import default_schema_path, default_policy_path, validate_record

root = Path(__file__).resolve().parents[1]
assert root / "src" not in Path(bioevidence_validator.__file__).resolve().parents
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
