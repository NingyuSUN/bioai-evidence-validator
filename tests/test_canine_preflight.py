"""The new CLI must expose missing work instead of silently dropping events."""
import json
from pathlib import Path

import pytest
from test_canine import ACCESSION, digest, fixture, rebind

from bioevidence_validator.canine_preflight import validate_canine_preflight
from bioevidence_validator.cli import main
from bioevidence_validator.grounding import SnapshotStore


def test_cli_keeps_pending_event_visible(tmp_path):
    doc = {'format_version': 'canine-preflight-1', 'taxon': 'NCBITaxon:9615',
           'catalogue': [{'id': 'pending:1', 'required_checks': ['dosage']}]}
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(doc))
    snapshots = tmp_path / 'sources'
    snapshots.mkdir()
    output = tmp_path / 'report.json'
    assert main(['canine-preflight', str(source), '--snapshot-dir', str(snapshots), '--output', str(output)]) == 2
    report = json.loads(output.read_text())
    assert report['catalogue_event_count'] == 1
    assert report['events'][0]['checks']['dosage']['status'] == 'not_assessed'



def packet(edit='102C>T', end=202):
    panel, raw = fixture(f'{ACCESSION}:g.{edit}')
    panel['events'][0]['target_end1'] = end
    return {'format_version': 'canine-preflight-1', 'taxon': 'NCBITaxon:9615',
            'catalogue': [{'id': 'authored:1', 'required_checks': ['source_reference', 'allele_reconstruction']}],
            'panel': panel}, raw


def run(doc, raw):
    return validate_canine_preflight(doc, SnapshotStore({k: lambda v=v: v for k, v in raw.items()}))


def pin(raw, data):
    value = data if isinstance(data, bytes) else json.dumps(data).encode()
    raw[digest(value)] = value
    return digest(value)


@pytest.mark.parametrize('edit,end,want', [
    ('102C>T', 202, 'AATCGGTTAACCGGTT'), ('102_103del', 203, 'AAGGTTAACCGGTT'),
    ('102_103dup', 203, 'AACCCCGGTTAACCGGTT'), ('102_104inv', 204, 'AACGGGTTAACCGGTT'),
    ('102_103insAT', 203, 'AACATCGGTTAACCGGTT'), ('102_103delinsAT', 203, 'AAATGGTTAACCGGTT'),
    ('[102C>T;104_105del]', 205, 'AATCTTAACCGGTT'), ('[104_105del;102C>T]', 205, 'AATCTTAACCGGTT'),
    ('[102_103del;110C>T]', 210, 'AAGGTTAATCGGTT'),
])
def test_entire_mutant_including_unchanged_flanks_and_intervening_bases(edit, end, want):
    doc, raw = packet(edit, end)
    row = run(doc, raw)['events'][0]
    assert row['checks']['allele_reconstruction']['status'] == 'verified'
    assert row['reconstructed_source_mutant'] == want
    if edit.startswith('['): assert row['overall_status'] == 'review_required'


def test_compound_supplied_alleles_are_actually_checked():
    doc, raw = packet('[102C>T;104_105del]', 205)
    doc['panel']['events'][0].update(event_ref='CCGG', event_alt='TC')
    assert run(doc, raw)['events'][0]['checks']['allele_reconstruction']['status'] == 'verified'
    doc['panel']['events'][0]['event_alt'] = 'TT'
    assert run(doc, raw)['overall_status'] == 'rejected'


@pytest.mark.parametrize('edit,end', [('102_103insN[1000000]', 203), ('102A[5]', 202), ('[102_103del;103C>T]', 203)])
def test_unknown_repeats_or_overlap_cannot_be_reconstructed(edit, end):
    doc, raw = packet(edit, end)
    row = run(doc, raw)['events'][0]
    assert row['checks']['allele_reconstruction']['status'] == 'review_required'
    assert 'reconstructed_source_mutant' not in row


@pytest.mark.parametrize('sequence,status', [(b'AATCGGTTAACCGGTA','rejected'), (b'AATCGGTTAACCGGTT','verified'),
                                            (b'AATCGGTTAACCGGTN','rejected')])
def test_complete_supplied_mutant_snapshot_compared(sequence, status):
    doc, raw = packet()
    doc['allele_requests'] = [{'event_id': 'authored:1', 'source_mutant_snapshot_sha256': pin(raw, sequence)}]
    assert run(doc, raw)['overall_status'] == status


@pytest.mark.parametrize('pos,ref,alt,status', [(202,'C','T','verified'), (202,'A','T','rejected'),
                                               (203,'C','T','rejected'), (202,'C','C','rejected'), (999,'C','T','review_required')])
def test_target_vcf_edit_replayed_against_full_source_mutant(pos, ref, alt, status):
    doc, raw = packet()
    doc['allele_requests'] = [{'event_id': 'authored:1', 'target_variant': {'chrom': 'chr14', 'pos1': pos, 'ref': ref, 'alt': alt}}]
    assert run(doc, raw)['events'][0]['checks']['target_equivalence']['status'] == status


def test_reverse_strand_target_edit_compared_in_source_orientation():
    panel, raw = fixture(f'{ACCESSION}:g.102C>T', strand='-')
    doc, _ = packet(); doc['panel'] = panel
    doc['allele_requests'] = [{'event_id': 'authored:1', 'target_variant': {'chrom': 'chr14', 'pos1': 213, 'ref': 'G', 'alt': 'A'}}]
    assert run(doc, raw)['events'][0]['checks']['target_equivalence']['status'] == 'verified'


def test_held_issue_and_wt_mismatch_survive_mutant_reconstruction():
    doc, raw = packet()
    doc['panel']['events'][0]['held_reasons'] = ['case exon identity unresolved']
    report = run(doc, raw)
    assert report['overall_status'] == 'review_required'
    assert any('case exon identity' in x['message'] for x in report['events'][0]['findings'])
    target = json.loads(raw[doc['panel']['references'][1]['snapshot_sha256']])
    target['queries']['case'].update(sequence='TACCGGTTAACCGGTT', sequence_sha256=digest(b'TACCGGTTAACCGGTT'))
    rebind(doc['panel'], raw, 1, target)
    assert run(doc, raw)['overall_status'] == 'rejected'


def test_unrepresented_events_and_unimplemented_checks_remain_in_denominators():
    doc, raw = packet()
    doc['catalogue'].append({'id': 'pending:2', 'required_checks': ['source_reference', 'dosage']})
    doc['catalogue'][0]['required_checks'].extend(['capture_specificity','phase','assay_performance'])
    report = run(doc, raw)
    assert report['catalogue_event_count'] == 2 and report['panel_event_count'] == 1
    assert report['check_counts']['source_reference']['not_assessed'] == 1
    assert report['events'][1]['checks']['dosage']['status'] == 'not_assessed'
    assert report['overall_status'] == 'review_required'
    assert not any(report[k] for k in ['assay_validated','orderable','reportable','admission_assessed'])


@pytest.mark.parametrize('fault', ['duplicate_catalogue','extra_panel_event','orphan_request','duplicate_request',
                                   'unknown_check','false_readiness','symbolic_alt','multi_alt'])
def test_bad_scope_and_unsupported_vcf_rejected(fault):
    doc, raw = packet()
    request = {'event_id': 'authored:1', 'source_mutant_snapshot_sha256': pin(raw,b'AATCGGTTAACCGGTT')}
    if fault == 'duplicate_catalogue': doc['catalogue'] *= 2
    elif fault == 'extra_panel_event': doc['panel']['events'][0]['id'] = 'outside'
    elif fault == 'orphan_request': request['event_id'] = 'outside'; doc['allele_requests'] = [request]
    elif fault == 'duplicate_request': doc['allele_requests'] = [request,request]
    elif fault == 'unknown_check': doc['catalogue'][0]['required_checks'] = ['invented']
    elif fault == 'false_readiness': doc['reportable'] = True
    else:
        doc['allele_requests'] = [{'event_id': 'authored:1', 'target_variant': {'chrom': 'chr14','pos1':202,'ref':'C','alt':'<DEL>' if fault == 'symbolic_alt' else 'T,A'}}]
    with pytest.raises(ValueError): run(doc,raw)


def test_receipt_applicability_per_event_and_current_replay_still_runs():
    doc,raw = packet()
    doc['catalogue'].append({'id':'pending:2','required_checks':['dosage']})
    doc['previous_report_sha256'] = pin(raw,run(doc,raw))
    report = run(doc,raw)
    assert report['events'][0]['prior_receipt_applicability'] == 'same_inputs_and_implementation'
    assert report['current_checks_recomputed'] is True and report['prior_results_used_to_skip_checks'] is False
    doc['catalogue'][1]['required_checks'].append('phase')
    report = run(doc,raw)
    assert report['events'][0]['prior_receipt_applicability'] == 'same_inputs_and_implementation'
    assert report['events'][1]['prior_receipt_applicability'] == 'inputs_changed'
    doc['panel']['events'][0]['held_reasons'] = ['new conflicting evidence']
    assert run(doc,raw)['events'][0]['prior_receipt_applicability'] == 'inputs_changed'


def test_changed_code_missing_and_corrupt_receipts_cannot_claim_reuse():
    doc,raw = packet(); old = run(doc,raw)
    old['implementation_sha256']['canine_preflight.py'] = '0'*64
    doc['previous_report_sha256'] = pin(raw,old)
    assert run(doc,raw)['events'][0]['prior_receipt_applicability'] == 'implementation_changed'
    doc['previous_report_sha256'] = 'f'*64
    assert run(doc,raw)['events'][0]['prior_receipt_applicability'] == 'unavailable'
    raw['f'*64] = b'{}'
    assert run(doc,raw)['overall_status'] == 'rejected'


def test_old_pass_never_overrides_missing_current_reference():
    doc,raw = packet(); doc['previous_report_sha256'] = pin(raw,run(doc,raw))
    del raw[doc['panel']['references'][0]['snapshot_sha256']]
    row = run(doc,raw)['events'][0]
    assert row['prior_receipt_applicability'] == 'current_evidence_unavailable_or_invalid'
    assert row['overall_status'] == 'review_required'


def test_cli_cannot_overwrite_input(tmp_path):
    doc,raw = packet(); source = tmp_path/'input.json'; source.write_text(json.dumps(doc))
    snapshots = tmp_path/'snapshots'; snapshots.mkdir()
    for k,v in raw.items(): (snapshots/k).write_bytes(v)
    assert main(['canine-preflight',str(source),'--snapshot-dir',str(snapshots),'--output',str(source)]) == 3
    assert json.loads(source.read_text()) == doc


def test_real_source_examples_reconstruct_and_retain_holds():
    root = Path(__file__).resolve().parents[1]/'examples/canine_panel'
    panel = json.loads((root/'panel.json').read_text())
    doc = {'format_version':'canine-preflight-1','taxon':'NCBITaxon:9615','panel':panel,
           'catalogue':[{'id':e['id'],'required_checks':['source_reference','allele_reconstruction']}for e in panel['events']]}
    report = validate_canine_preflight(doc,SnapshotStore.from_directory(root/'sources'))
    assert report['check_counts']['allele_reconstruction']['verified'] == 6
    assert report['event_status_counts'] == {'verified':4,'review_required':2,'rejected':0}


@pytest.mark.parametrize('field', ['pos1', 'target_start1', 'target_end1'])
def test_integral_float_coordinates_are_invalid_input_not_runtime_crashes(field):
    doc, raw = packet()
    if field == 'pos1':
        doc['allele_requests'] = [{'event_id':'authored:1','target_variant':{'chrom':'chr14','pos1':202.0,'ref':'C','alt':'T'}}]
    else:
        doc['panel']['events'][0][field] = 202.0
    with pytest.raises(ValueError): run(doc, raw)


def test_cli_integral_float_returns_input_error(tmp_path):
    doc, raw = packet(); doc['panel']['events'][0]['target_start1'] = 202.0
    source = tmp_path/'input.json'; source.write_text(json.dumps(doc))
    snapshots = tmp_path/'sources'; snapshots.mkdir()
    for key, value in raw.items(): (snapshots/key).write_bytes(value)
    assert main(['canine-preflight',str(source),'--snapshot-dir',str(snapshots)]) == 3


@pytest.mark.parametrize('old', [{}, {'format_version':'canine-preflight-report-1','events':[{}],'implementation_sha256':{}},
                                 b'{"format_version":NaN}', b'{"events":[],"events":[]}'])
def test_malformed_old_report_cannot_be_used_for_applicability(old):
    doc, raw = packet(); doc['previous_report_sha256'] = pin(raw, old)
    report = run(doc, raw)
    assert report['overall_status'] == 'rejected'
    assert report['events'][0]['checks']['allele_reconstruction']['status'] == 'verified'


def test_new_event_has_no_prior_report_binding():
    doc,raw = packet(); doc['previous_report_sha256'] = pin(raw,run(doc,raw))
    doc['catalogue'].append({'id':'new:2','required_checks':['dosage']})
    assert run(doc,raw)['events'][1]['prior_receipt_applicability'] == 'event_not_in_prior_report'


def test_old_claimed_pass_cannot_supply_unimplemented_checks():
    doc,raw = packet(); doc['catalogue'][0]['required_checks'].append('dosage')
    previous = run(doc,raw)
    previous['events'][0]['checks']['dosage']['status'] = 'verified'
    previous['events'][0]['overall_status'] = 'verified'
    doc['previous_report_sha256'] = pin(raw,previous)
    report = run(doc,raw)
    assert report['events'][0]['prior_receipt_applicability'] == 'same_inputs_and_implementation'
    assert report['events'][0]['checks']['dosage']['status'] == 'not_assessed'
    assert report['overall_status'] == 'review_required'


def test_missing_mutant_snapshot_and_wrong_source_accession_remain_unresolved():
    doc,raw = packet()
    doc['allele_requests'] = [{'event_id':'authored:1','source_mutant_snapshot_sha256':'f'*64}]
    assert run(doc,raw)['events'][0]['checks']['allele_reconstruction']['status'] == 'review_required'
    doc['panel']['events'][0]['source_hgvs'] = 'NC_049235.2:g.102C>T'
    assert run(doc,raw)['events'][0]['checks']['allele_reconstruction']['status'] == 'rejected'


def test_target_request_does_not_clear_failed_reference_or_unknown_payload():
    doc,raw = packet('102_103insN[10]',203)
    doc['allele_requests'] = [{'event_id':'authored:1','target_variant':{'chrom':'chr14','pos1':202,'ref':'C','alt':'CAT'}}]
    assert run(doc,raw)['events'][0]['checks']['target_equivalence']['status'] == 'review_required'
    doc,raw = packet()
    del doc['panel']['events'][0]['target_reference']
    doc['allele_requests'] = [{'event_id':'authored:1','target_variant':{'chrom':'chr14','pos1':202,'ref':'C','alt':'T'}}]
    assert run(doc,raw)['events'][0]['checks']['target_equivalence']['status'] == 'review_required'


def test_absent_source_reference_cannot_reconstruct_or_reuse():
    doc,raw = packet(); doc['panel']['events'][0]['source_reference']='missing'
    previous = run(doc,raw); doc['previous_report_sha256']=pin(raw,previous)
    row=run(doc,raw)['events'][0]
    assert row['checks']['allele_reconstruction']['status']=='review_required'
    assert row['prior_receipt_applicability']=='current_evidence_unavailable_or_invalid'


def test_compound_success_does_not_repeat_obsolete_unchecked_diagnostic():
    doc,raw=packet('[102C>T;104_105del]',205)
    doc['panel']['events'][0].update(event_ref='CCGG',event_alt='TC')
    row=run(doc,raw)['events'][0]
    assert row['checks']['allele_reconstruction']['status']=='verified'
    assert not any(f['field_path']=='event_ref/event_alt' for f in row['findings'])
    assert any(f['field_path']=='event_ref/event_alt' for f in row['legacy_reference_findings'])
    assert row['overall_status']=='review_required'
