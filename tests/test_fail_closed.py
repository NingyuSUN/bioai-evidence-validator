import copy
import json
from pathlib import Path
import pytest
from bioevidence_validator.engine import validate_record

ROOT = Path(__file__).resolve().parents[1]

def valid():
    return json.loads((ROOT / 'examples/canine_breed/valid_labrador.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('uses', [[], ['unknown_use'], ['display_name', 'unknown_use'], None, 'display_name', [123], ['display_name', 'display_name']])
def test_invalid_requested_uses_never_admit(uses):
    record = valid()
    record['requested_uses'] = uses
    report = validate_record(record)
    assert report['overall_status'] == 'rejected'
    assert report['findings']
    assert all(d['admission_status'] == 'rejected' for d in report['use_decisions'])

@pytest.mark.parametrize('record', [None, [], 'text', 123, True])
def test_non_object_json_returns_rejection(record):
    report = validate_record(record)
    assert report['overall_status'] == 'rejected'
    assert report['schema_valid'] is False

@pytest.mark.parametrize('field', ['requested_uses', 'source_artifacts', 'evidence_items'])
def test_missing_required_collections_returns_rejection(field):
    record = valid()
    del record[field]
    assert validate_record(record)['overall_status'] == 'rejected'

@pytest.mark.parametrize('field', ['source_artifacts', 'evidence_items'])
def test_duplicate_evidence_identifiers_are_not_silently_overwritten(field):
    record = valid()
    duplicate = copy.deepcopy(record[field][0])
    if field == 'source_artifacts':
        duplicate['sha256'] = 'd' * 64
    else:
        duplicate['extraction_method'] = 'normalized_string_match'
    record[field].append(duplicate)
    report = validate_record(record)
    assert report['overall_status'] == 'rejected'
    assert 'RECORD_INTEGRITY' in {f['rule_id'] for f in report['findings']}

@pytest.mark.parametrize('field', ['source_artifacts', 'evidence_items'])
def test_empty_evidence_collections_return_rejection(field):
    record = valid()
    record[field] = []
    assert validate_record(record)['overall_status'] == 'rejected'

@pytest.mark.parametrize('field', ['source_artifacts', 'evidence_items'])
def test_null_required_collections_are_rejected(field):
    record = valid()
    record[field] = None
    assert validate_record(record)['overall_status'] == 'rejected'


def test_optional_null_collections_behave_like_absent_fields():
    record = valid()
    record['adjudications'] = None
    record['statement']['object_breed']['scope_flags'] = None
    assert validate_record(record)['overall_status'] == 'admitted'


def test_invalid_policy_does_not_silently_disable_checks(tmp_path):
    policy = tmp_path / 'policy.yaml'
    policy.write_text('id: test\nversion: "1"\nrules:\n  CBR001:\n    enabled: "false"\n    severity: typo\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Policy rule'):
        validate_record(valid(), policy_path=policy)


@pytest.mark.parametrize("path", [("statement", "evidence_lines"), ("statement", "subject_label", "source_scope"), ("statement", "subject_label", "candidate_concept_ids")])
@pytest.mark.parametrize("missing", [True, False])
def test_nested_required_evidence_is_rejected(path, missing):
    record = valid()
    target = record
    for key in path[:-1]:
        target = target[key]
    if missing:
        del target[path[-1]]
    else:
        target[path[-1]] = None
    assert validate_record(record)["overall_status"] == "rejected"

@pytest.mark.parametrize('status', ['rejected', 'superseded'])
def test_withdrawn_statement_is_not_admitted(status):
    record = valid()
    record['statement']['statement_status'] = status
    assert validate_record(record)['overall_status'] == 'rejected'


def decision(name, value):
    return {'id': 'bioev:' + name, 'decision': value,
            'reviewer': {'id': 'bioev:human-reviewer', 'agent_type': 'human'},
            'rationale': 'Synthetic review for regression.', 'decided_at': '2026-09-21T00:00:00Z'}


@pytest.mark.parametrize('decisions,expected', [(['accept'], 'admitted'), (['accept', 'reject'], 'rejected'), (['reject', 'accept'], 'rejected'), (['accept', 'defer'], 'review_required')])
def test_acceptance_never_erases_conflicting_human_decisions(decisions, expected):
    record = valid()
    record['requested_uses'] = ['training_label']
    record['statement']['subject_label']['genotype_membership_verified'] = True
    record['adjudications'] = [decision(str(i), value) for i, value in enumerate(decisions)]
    assert validate_record(record)['overall_status'] == expected


def test_unresolved_concept_requires_review():
    record = valid()
    record['statement']['object_breed']['concept_status'] = 'unresolved'
    assert validate_record(record)['overall_status'] == 'review_required'


def test_policy_and_schema_versions_are_auditable():
    report = validate_record(valid())
    assert report['policy_version'] == '0.2.0'
    assert report['schema_version'] == '0.2.0'
    assert len(report['schema_sha256']) == 64
