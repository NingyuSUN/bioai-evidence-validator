import json
from pathlib import Path

import pytest

from bioevidence_validator.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_writes_audit_report(tmp_path):
    output = tmp_path / "report.json"
    code = main([
        "validate",
        str(ROOT / "examples" / "general" / "curated_assertion.json"),
        "--output",
        str(output),
    ])
    assert code == 0
    report = json.loads(output.read_text())
    assert report["profile_id"] == "general"
    assert len(report["profile_sha256"]) == 64
    assert len(report["input_sha256"]) == 64


def test_cli_exit_code_distinguishes_rejection(tmp_path):
    output = tmp_path / "report.json"
    code = main([
        "validate",
        str(ROOT / "examples" / "dataset_label" / "missing_sample_link.json"),
        "--profile", "dataset-label",
        "--output",
        str(output),
    ])
    assert code == 1
    assert json.loads(output.read_text())["overall_status"] == "rejected"


@pytest.mark.parametrize('payload', ['{bad json', '{"requested_uses": [], "requested_uses": ["display_name"]}', '{"score": NaN}'])
def test_cli_invalid_json_returns_operational_error(tmp_path, capsys, payload):
    source = tmp_path / 'bad.json'
    output = tmp_path / 'report.json'
    source.write_text(payload, encoding='utf-8')
    assert main(['validate', str(source), '--output', str(output)]) == 3
    assert not output.exists()
    assert json.loads(capsys.readouterr().err)['error'] == 'input_or_execution_error'


def test_cli_missing_file_has_no_traceback(tmp_path, capsys):
    assert main(['validate', str(tmp_path / 'missing.json')]) == 3
    assert 'Traceback' not in capsys.readouterr().err


def test_cli_rejects_empty_uses_with_audit_report(tmp_path):
    record = json.loads((ROOT / 'examples/general/curated_assertion.json').read_text(encoding='utf-8'))
    record['requested_uses'] = []
    source, output = tmp_path / 'record.json', tmp_path / 'report.json'
    source.write_text(json.dumps(record), encoding='utf-8')
    assert main(['validate', str(source), '--output', str(output)]) == 1
    assert json.loads(output.read_text(encoding='utf-8'))['overall_status'] == 'rejected'


def test_cli_preserves_input_when_output_aliases_it(tmp_path):
    source = tmp_path / 'record.json'
    source.write_bytes((ROOT / 'examples/general/curated_assertion.json').read_bytes())
    before = source.read_bytes()
    assert main(['validate', str(source), '--output', str(source)]) == 3
    assert source.read_bytes() == before


def test_cli_accepts_utf8_input_and_emits_lf_report(tmp_path):
    record = json.loads((ROOT / 'examples/general/curated_assertion.json').read_text(encoding='utf-8'))
    record['statement']['subject']['label'] = 'ラブラドール / 拉布拉多'
    source, output = tmp_path / 'record.json', tmp_path / 'report.json'
    source.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    assert main(['validate', str(source), '--output', str(output)]) == 0
    assert b'\r\n' not in output.read_bytes()
    assert json.loads(output.read_text(encoding='utf-8'))['overall_status'] == 'admitted'


def test_cli_review_exit_code_has_review_report(tmp_path):
    record = json.loads((ROOT / 'examples/general/curated_assertion.json').read_text(encoding='utf-8'))
    record['statement']['evidence_lines'][0]['direction'] = 'contradicts'
    source, output = tmp_path / 'record.json', tmp_path / 'report.json'
    source.write_text(json.dumps(record), encoding='utf-8')
    assert main(['validate', str(source), '--output', str(output)]) == 2
    assert json.loads(output.read_text(encoding='utf-8'))['overall_status'] == 'review_required'


def test_failed_report_replace_keeps_previous_report(tmp_path, monkeypatch):
    from bioevidence_validator import cli
    output = tmp_path / 'report.json'
    output.write_text('previous report', encoding='utf-8')
    def fail(*args):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(cli.os, 'replace', fail)
    code = main(['validate', str(ROOT / 'examples/general/curated_assertion.json'), '--output', str(output)])
    assert code == 3
    assert output.read_text(encoding='utf-8') == 'previous report'
    assert list(tmp_path.iterdir()) == [output]



def test_profiles_lists_packaged_contracts(capsys):
    assert main(['profiles']) == 0
    profiles = json.loads(capsys.readouterr().out)
    assert {p['id'] for p in profiles} == {'general', 'literature-claim', 'dataset-label'}


def test_custom_profile_through_cli():
    assert main(['validate', str(ROOT / 'examples/custom_profile/assay_record.json'),
                 '--profile', str(ROOT / 'examples/custom_profile/assay.yaml')]) == 0


@pytest.mark.parametrize('target', ['profile', 'schema'])
def test_cli_protects_configuration_files(tmp_path, target):
    from bioevidence_validator.engine import default_schema_path, profile_path
    profile, schema = tmp_path / 'profile.yaml', tmp_path / 'schema.yaml'
    profile.write_bytes(profile_path().read_bytes()); schema.write_bytes(default_schema_path().read_bytes())
    output = profile if target == 'profile' else schema
    before = output.read_bytes()
    assert main(['validate', str(ROOT / 'examples/general/curated_assertion.json'),
                 '--profile', str(profile), '--schema', str(schema), '--output', str(output)]) == 3
    assert output.read_bytes() == before


def test_schema_generation_and_compilation_error(tmp_path, capsys):
    output = tmp_path / 'schema.json'
    assert main(['generate-schema', '--output', str(output)]) == 0
    assert 'BioEvidenceRecord' in json.loads(output.read_text(encoding='utf-8'))['$defs']
    malformed = tmp_path / 'bad.yaml'; malformed.write_text('broken: [', encoding='utf-8')
    before = output.read_bytes()
    assert main(['generate-schema', '--schema', str(malformed), '--output', str(output)]) == 3
    assert json.loads(capsys.readouterr().err)['error'] == 'input_or_execution_error'
    assert output.read_bytes() == before


@pytest.mark.parametrize('depth', [101, 5000, 100_000])
def test_deep_json_fails_with_structured_error(tmp_path, capsys, depth):
    source = tmp_path / 'deep.json'; source.write_text('[' * depth + ']' * depth, encoding='utf-8')
    assert main(['validate', str(source)]) == 3
    assert json.loads(capsys.readouterr().err)['error'] == 'input_or_execution_error'


def test_json_at_depth_limit_reaches_validation(tmp_path):
    source = tmp_path / 'deep.json'; source.write_text('[' * 100 + ']' * 100, encoding='utf-8')
    assert main(['validate', str(source)]) == 1
