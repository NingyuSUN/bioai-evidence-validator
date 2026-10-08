"""Whole-catalogue engineering preflight and complete supported-allele replay.

Prior reports are compared for applicability, never trusted instead of replay.
This module does not authenticate sources or establish phase/assay performance.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .canine import (
    HASH,
    TEXT,
    Edit,
    SequenceSlice,
    VariantProblem,
    _unique_json,
    load_reference,
    parse_genomic_hgvs,
    reverse_complement,
    sha,
    validate_canine_panel,
)
from .canine import SCHEMA as PANEL_SCHEMA
from .grounding import SnapshotStore

CHECKS = ('source_reference', 'allele_reconstruction', 'target_equivalence',
          'capture_specificity', 'dosage', 'phase', 'assay_performance')
STATUSES = ('verified', 'review_required', 'rejected', 'not_assessed')
BASES = {'type': 'string', 'pattern': '^[ACGT]+$'}
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['format_version', 'taxon', 'catalogue'],
    'properties': {
        'format_version': {'const': 'canine-preflight-1'}, 'taxon': {'const': 'NCBITaxon:9615'},
        'catalogue': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['id', 'required_checks'],
            'properties': {'id': TEXT, 'required_checks': {'type': 'array', 'minItems': 1,
                           'uniqueItems': True, 'items': {'enum': list(CHECKS)}}}}},
        'panel': PANEL_SCHEMA,
        'allele_requests': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['event_id'], 'minProperties': 2,
            'properties': {'event_id': TEXT, 'source_mutant_snapshot_sha256': HASH,
                'target_variant': {'type': 'object', 'additionalProperties': False,
                    'required': ['chrom', 'pos1', 'ref', 'alt'],
                    'properties': {'chrom': TEXT, 'pos1': {'type': 'integer', 'minimum': 1, 'maximum': 10**18-1},
                                   'ref': BASES, 'alt': BASES}}}}},
        'previous_report_sha256': HASH,
    },
}


def _hash(value: Any) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())


def _finding(problem: VariantProblem, field: str) -> dict:
    return {'rule_id': problem.code, 'severity': 'review' if problem.code == 'BEV015' else 'error',
            'message': str(problem), 'field_path': field}


def _bytes(key: str, store: SnapshotStore) -> bytes:
    data = store.get(key)
    if data is None:
        raise VariantProblem('BEV015', 'The declared snapshot is unavailable.')
    if not store.verified(key):
        raise VariantProblem('BEV014', 'Snapshot bytes differ from the declared SHA-256.')
    return data


def _mutant(source: SequenceSlice, edits: list[Edit]) -> str:
    """Apply all original-coordinate edits, retaining untouched intervening bases."""
    source.interval(source.start1, source.end1)  # also reject ambiguous full contexts
    cursor = 0
    pieces = []
    for edit in sorted(edits, key=lambda e: e.start1):
        reference = source.interval(edit.start1, edit.end1)
        if edit.ref is not None and edit.ref != reference:
            raise VariantProblem('BEV017', 'Source edit REF differs from the pinned reference.')
        left, right = edit.start1-source.start1, edit.end1-source.start1+1
        if edit.operation == 'ins':
            left = right = left+1  # insert between adjacent flanks, after the left base
        if edit.operation in {'ins', 'delins', 'substitution'}:
            if edit.inserted is None:
                raise VariantProblem('BEV015', 'Unknown inserted bases prevent complete allele reconstruction.')
            replacement = edit.inserted
        elif edit.operation == 'del':
            replacement = ''
        elif edit.operation == 'dup':
            replacement = reference*2
        else:  # the parser admits only inversion as the remaining operation
            replacement = reverse_complement(reference)
        pieces.extend([source.sequence[cursor:left], replacement])
        cursor = right
    pieces.append(source.sequence[cursor:])
    return ''.join(pieces)


def _reconstruct(event: dict, specs: dict, store: SnapshotStore) -> tuple[str, SequenceSlice]:
    accession, edits = parse_genomic_hgvs(event.get('reviewed_hgvs', event['source_hgvs']))
    spec = specs.get(event.get('source_reference'))
    if spec is None:
        raise VariantProblem('BEV015', 'No source reference was supplied for reconstruction.')
    source = load_reference(spec, store)
    if accession != source.sequence_id or source.assembly != event['source_assembly']:
        raise VariantProblem('BEV017', 'Source accession/version or assembly differs from the pinned slice.')
    mutant = _mutant(source, edits)
    if len(edits) > 1:
        left = min(e.start1 for e in edits)-source.start1
        trailing = source.end1-max(e.end1 for e in edits)
        reference = source.sequence[left:len(source.sequence)-trailing]
        altered = mutant[left:len(mutant)-trailing]
        if ('event_ref' in event and event['event_ref'] != reference
                or 'event_alt' in event and event['event_alt'] != altered):
            raise VariantProblem('BEV017', 'Declared compound REF/ALT differs from the reconstructed outer event span.')
    return mutant, source


def _target(event: dict, request: dict, legacy: dict, mutant: str, specs: dict, store: SnapshotStore) -> dict:
    if legacy['source_target_context_status'] != 'VERIFIED_ORIENTED_COMPLETE_SLICE':
        raise VariantProblem('BEV015', 'Whole source/target WT contexts must agree before mutant equivalence can pass.')
    target = load_reference(specs[event['target_reference']], store)
    variant = request['target_variant']
    if variant['chrom'] != target.sequence_id or variant['ref'] == variant['alt']:
        raise VariantProblem('BEV017', 'Target chromosome differs or target REF and ALT do not describe a change.')
    actual = target.interval(variant['pos1'], variant['pos1']+len(variant['ref'])-1)
    if actual != variant['ref']:
        raise VariantProblem('BEV017', 'Target VCF REF differs from the pinned target sequence.')
    offset = variant['pos1']-target.start1
    altered = target.sequence[:offset]+variant['alt']+target.sequence[offset+len(variant['ref']):]
    oriented = altered if event['target_strand'] == '+' else reverse_complement(altered)
    if oriented != mutant:
        raise VariantProblem('BEV017', 'Entire reconstructed source and oriented target mutant contexts differ.')
    return {'status': 'verified', 'reason': 'Entire source and target mutant contexts agree.',
            'target_mutant_sha256': sha(altered.encode()), 'oriented_mutant_sha256': sha(oriented.encode())}


def _index(rows: list[dict], key: str, label: str) -> dict:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate '+label+' identifier')
    return result


def _prior(document: dict, store: SnapshotStore) -> tuple[dict | None, str, list]:
    if 'previous_report_sha256' not in document:
        return None, 'not_supplied', []
    try:
        raw = _bytes(document['previous_report_sha256'], store)
        old = json.loads(raw, object_pairs_hook=_unique_json,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
        if (not isinstance(old, dict) or old.get('format_version') != 'canine-preflight-report-1'
                or not isinstance(old.get('events'), list) or not isinstance(old.get('implementation_sha256'), dict)):
            raise ValueError('Unexpected prior report format')
        for row in old['events']:
            if (not isinstance(row, dict) or not isinstance(row.get('id'), str)
                    or not isinstance(row.get('event_fingerprint'), str)
                    or re.fullmatch('[0-9a-f]{64}', row['event_fingerprint']) is None):
                raise ValueError('Invalid prior event binding')
        old['by_id'] = _index(old['events'], 'id', 'prior report event')
        return old, 'available', []
    except (VariantProblem, ValueError, UnicodeError, RecursionError) as error:
        problem = error if isinstance(error, VariantProblem) else VariantProblem('BEV024', 'Malformed prior report: '+str(error))
        return None, 'unavailable' if problem.code == 'BEV015' else 'invalid', [_finding(problem, 'previous_report_sha256')]


def _applicability(prior: dict | None, state: str, row: dict, implementation: dict, evidence_usable: bool) -> str:
    if prior is None:
        return state
    if not evidence_usable:
        return 'current_evidence_unavailable_or_invalid'
    old = prior['by_id'].get(row['id'])
    if old is None:
        return 'event_not_in_prior_report'
    if old['event_fingerprint'] != row['event_fingerprint']:
        return 'inputs_changed'
    if prior['implementation_sha256'] != implementation:
        return 'implementation_changed'
    return 'same_inputs_and_implementation'


def validate_canine_preflight(document: dict[str, Any], store: SnapshotStore) -> dict[str, Any]:
    """Account for the declared event universe and recompute supported checks."""
    errors = list(Draft202012Validator(SCHEMA).iter_errors(document))
    if errors:
        raise ValueError('Invalid canine-preflight input: '+'; '.join(e.message for e in errors))
    catalogue = _index(document['catalogue'], 'id', 'catalogue')
    panel = document.get('panel', {'events': [], 'references': []})
    events = _index(panel['events'], 'id', 'panel event')
    specs = _index(panel['references'], 'id', 'reference')
    requests = _index(document.get('allele_requests', []), 'event_id', 'allele request')
    for event in events.values():
        for field in ('target_start1', 'target_end1'):
            if field in event and type(event[field]) is not int:
                raise ValueError('Panel target coordinates must be JSON integers, not integral floats.')
    for request in requests.values():
        if 'target_variant' in request and type(request['target_variant']['pos1']) is not int:
            raise ValueError('Target variant position must be a JSON integer, not an integral float.')
    if set(events)-set(catalogue) or set(requests)-set(events):
        raise ValueError('Panel events must belong to the catalogue; allele requests must belong to panel events.')
    legacy = validate_canine_panel(panel, store) if 'panel' in document else None
    legacy_rows = {e['id']: e for e in legacy['events']} if legacy else {}
    implementation = {name: sha(Path(__file__).with_name(name).read_bytes())
                      for name in ('canine_preflight.py', 'canine.py', 'grounding.py')}
    prior, prior_state, findings = _prior(document, store)
    if legacy:
        findings.extend(legacy['reference_findings'])
    rows = []
    for identifier, entry in catalogue.items():
        event, request = events.get(identifier), requests.get(identifier, {})
        used_specs = {name: specs.get(name) for name in sorted({event[k] for k in
                      ('source_reference', 'target_reference') if event and k in event})}
        basis = {'format_version': document['format_version'], 'taxon': document['taxon'],
                 'catalogue_entry': entry, 'event': event, 'request': request, 'references': used_specs}
        row: dict[str, Any] = {'id': identifier, 'required_checks': entry['required_checks'],
            'event_fingerprint': _hash(basis), 'checks': {name: {'status': 'not_assessed',
            'reason': 'No executable evidence supplied or check not implemented by this entry.'} for name in CHECKS},
            'findings': [], 'assay_validated': False, 'orderable': False, 'reportable': False}
        evidence_usable = True
        for spec in used_specs.values():
            if spec is None:
                evidence_usable = False
                continue
            try:
                load_reference(spec, store)
            except VariantProblem:
                evidence_usable = False
        if event:
            base = legacy_rows[identifier]
            row['legacy_reference_findings'] = list(base['findings'])
            row['findings'] = list(base['findings'])
            row['legacy_reference_status'] = base['engineering_status']
            row['checks']['source_reference'] = {'status': 'verified' if base['source_reference_status'] ==
                'VERIFIED_WITHIN_PINNED_SLICE' else 'rejected' if base['engineering_status'] == 'rejected' else 'review_required',
                'reason': base['source_reference_status']}
            try:
                mutant, source = _reconstruct(event, specs, store)
                row['reconstructed_source_mutant'] = mutant
                row['source_mutant_sha256'] = sha(mutant.encode())
                row['source_mutant_length_bp'] = len(mutant)
                row['source_reference_binding'] = source.binding
                if 'source_mutant_snapshot_sha256' in request:
                    supplied = _bytes(request['source_mutant_snapshot_sha256'], store)
                    if supplied != mutant.encode():
                        raise VariantProblem('BEV017', 'Supplied complete mutant snapshot differs from reconstructed source bytes.')
                row['checks']['allele_reconstruction'] = {'status': 'verified',
                    'reason': 'All supported edits applied to the full source slice; physical phase remains unverified.'}
                # The old check remains archived; the new computation resolves only
                # its compound-payload limitation, never a source or phase hold.
                row['findings'] = [f for f in row['findings'] if not (
                    f['field_path'] == 'event_ref/event_alt' and f['rule_id'] == 'BEV015')]
            except VariantProblem as problem:
                row['checks']['allele_reconstruction'] = {'status': 'review_required' if problem.code == 'BEV015' else 'rejected',
                                                        'reason': str(problem)}
                row['findings'].append(_finding(problem, 'allele_reconstruction'))
                if 'source_mutant_snapshot_sha256' in request:
                    evidence_usable = False
            if 'target_variant' in request:
                try:
                    if row['checks']['allele_reconstruction']['status'] != 'verified':
                        raise VariantProblem('BEV015', 'Complete source allele reconstruction is unresolved.')
                    row['checks']['target_equivalence'] = _target(event, request, base,
                        row['reconstructed_source_mutant'], specs, store)
                except VariantProblem as problem:
                    row['checks']['target_equivalence'] = {'status': 'review_required' if problem.code == 'BEV015' else 'rejected',
                                                          'reason': str(problem)}
                    row['findings'].append(_finding(problem, 'target_equivalence'))
        required = [row['checks'][k]['status'] for k in entry['required_checks']]
        row['overall_status'] = ('rejected' if any(f['severity'] == 'error' for f in row['findings']) else
            'review_required' if row['findings'] or any(s != 'verified' for s in required) else 'verified')
        row['prior_receipt_applicability'] = _applicability(prior, prior_state, row, implementation, evidence_usable)
        rows.append(row)
    counts = {s: sum(r['overall_status'] == s for r in rows) for s in STATUSES[:3]}
    overall = ('rejected' if counts['rejected'] or any(f['severity'] == 'error' for f in findings) else
               'review_required' if counts['review_required'] or findings else 'verified')
    return {'format_version': 'canine-preflight-report-1', 'overall_status': overall,
        'input_sha256': _hash(document), 'implementation_sha256': implementation,
        'catalogue_event_count': len(catalogue), 'panel_event_count': len(events), 'events': rows,
        'event_status_counts': counts, 'check_counts': {k: {s: sum(r['checks'][k]['status'] == s for r in rows)
                                                      for s in STATUSES} for k in CHECKS},
        'findings': findings, 'current_checks_recomputed': True, 'prior_results_used_to_skip_checks': False,
        'scope': 'Declared catalogue accounting, supported whole-allele replay and prior-input applicability only.',
        'limitations': ['Catalogue completeness depends on the supplied event universe.',
            'Pinned producer receipts do not authenticate producers or the whole genome.',
            'Prior applicability is not prior result authenticity or validation acceptance.',
            'Capture specificity, dosage, physical phase and assay performance are not assessed.',
            'No HGVS/VCF normalization or independent clinical truth is established.'],
        'locus_contracts_frozen': False, 'admission_assessed': False, 'assay_validated': False,
        'probe_ready': False, 'orderable': False, 'reportable': False}
