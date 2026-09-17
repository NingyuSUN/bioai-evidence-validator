import json
from pathlib import Path

from bioevidence_validator.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_cli_writes_audit_report(tmp_path):
    output = tmp_path / "report.json"
    code = main([
        "validate",
        str(ROOT / "examples" / "canine_breed" / "valid_labrador.json"),
        "--output",
        str(output),
    ])
    assert code == 0
    report = json.loads(output.read_text())
    assert report["policy_id"] == "canine-breed-catalog"
    assert len(report["policy_sha256"]) == 64
    assert len(report["input_sha256"]) == 64


def test_cli_exit_code_distinguishes_rejection(tmp_path):
    output = tmp_path / "report.json"
    code = main([
        "validate",
        str(ROOT / "examples" / "canine_breed" / "ambiguous_boxer.json"),
        "--output",
        str(output),
    ])
    assert code == 1
    assert json.loads(output.read_text())["overall_status"] == "rejected"
