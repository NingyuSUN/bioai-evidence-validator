import copy

import pytest
import yaml
from test_engine import load

from bioevidence_validator.engine import RecordValidator, profile_path


@pytest.mark.parametrize('methods,code', [(['llm_extraction'], 'BEV008'), (['normalized_string_match'], 'BEV009'), (['llm_extraction', 'normalized_string_match'], 'BEV013')])
@pytest.mark.parametrize('auxiliary', ['manual_curation', 'deterministic_parser'])
def test_unrelated_strong_support_cannot_launder_required_weak_evidence(methods, code, auxiliary):
    record = load('literature_claim/curated_association.json')
    first = record['evidence_items'][0]; first['extraction_method'] = methods[0]
    refs = record['statement']['evidence_lines'][0]['evidence_item_ids']
    if len(methods) > 1:
        extra = copy.deepcopy(first); extra.update(id='bioev:weak2', extraction_method=methods[1])
        record['evidence_items'].append(extra); refs.append(extra['id'])
    note = copy.deepcopy(first); note.update(id='bioev:note', evidence_type='curator_note', extraction_method=auxiliary)
    record['evidence_items'].append(note); refs.append(note['id'])
    report = RecordValidator(profile='literature-claim').validate(record)
    assert report['overall_status'] == 'review_required'
    assert any(f['rule_id'] == code and 'publication_result' in f['message'] for f in report['findings'])


@pytest.mark.parametrize('direction,expected', [('supports', 'admitted'), ('neutral', 'review_required'), ('contradicts', 'review_required')])
def test_only_qualifying_support_for_same_type_can_strengthen_it(direction, expected):
    record = load('literature_claim/llm_only.json')
    reviewed = copy.deepcopy(record['evidence_items'][0]); reviewed.update(id='bioev:reviewed', extraction_method='manual_curation')
    record['evidence_items'].append(reviewed)
    record['statement']['evidence_lines'].append({'id':'bioev:reviewed-line','direction':direction,'evidence_item_ids':[reviewed['id']]})
    report = RecordValidator(profile='literature-claim').validate(record)
    assert report['overall_status'] == expected


def test_each_required_type_has_its_own_gate():
    record = load('dataset_label/curated_sample_label.json')
    record['evidence_items'][1]['extraction_method'] = 'llm_extraction'
    report = RecordValidator(profile='dataset-label').validate(record)
    assert report['overall_status'] == 'review_required'
    assert any(f['rule_id'] == 'BEV008' and 'sample_link' in f['message'] for f in report['findings'])


def test_quality_permissions_remain_use_specific(tmp_path):
    record = load('literature_claim/llm_only.json')
    record['requested_uses'] = ['research_summary', 'knowledge_base']
    profile = yaml.safe_load(profile_path('literature-claim').read_bytes())
    profile['uses']['research_summary']['allow_llm_only'] = True
    profile['uses']['knowledge_base']['require_human_acceptance'] = False
    path = tmp_path/'profile.yaml';path.write_text(yaml.safe_dump(profile),encoding='utf-8')
    report = RecordValidator(profile=path).validate(record)
    assert {d['use']:d['admission_status'] for d in report['use_decisions']} == {'research_summary':'admitted','knowledge_base':'review_required'}
