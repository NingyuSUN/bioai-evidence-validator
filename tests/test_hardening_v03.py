"""Regression cases discovered during the 0.3 hardening audit."""
import copy
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import yaml

from bioevidence_validator.engine import default_policy_path, validate_record
from bioevidence_validator.canine_panel_adapter import export_canine_panel
from test_canine_panel_adapter import make_database, make_manifest

ROOT = Path(__file__).resolve().parents[1]

def valid():
    return json.loads((ROOT/'examples/canine_breed/valid_labrador.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('case', ['neutral_only', 'wrong_candidate', 'mixed_scope', 'blank_label', 'blank_locator', 'dangling_unused_item', 'wrong_predicate'])
def test_unsupported_evidence_cannot_admit(case):
    record = valid()
    if case == 'neutral_only': record['statement']['evidence_lines'][0]['direction'] = 'neutral'
    elif case == 'wrong_candidate': record['statement']['object_breed']['concept_id'] = 'VBO:OTHER'
    elif case == 'mixed_scope': record['statement']['object_breed']['breed_scope'] = 'mixed_breed'
    elif case == 'blank_label': record['statement']['subject_label']['value'] = '  '
    elif case == 'blank_locator': record['evidence_items'][0]['locator'] = ' '
    elif case == 'wrong_predicate': record['statement']['predicate'] = 'variety_of'
    else:
        extra = copy.deepcopy(record['evidence_items'][0]); extra['id'] = 'bioev:unused'
        extra['source_artifact_id'] = 'bioev:absent'; record['evidence_items'].append(extra)
    assert validate_record(record)['overall_status'] != 'admitted'


def test_neutral_scope_evidence_cannot_support_regional_mapping():
    record = valid(); record['statement']['subject_label']['scope_hint'] = 'regional_population'
    record['statement']['statement_type'] = 'source_label_assignment'; record['statement']['predicate'] = 'maps_to_breed'
    item = copy.deepcopy(record['evidence_items'][0]); item['id'] = 'bioev:scope'; item['evidence_type'] = 'official_scope_statement'
    record['evidence_items'].append(item)
    record['statement']['evidence_lines'].append({'id':'bioev:neutral', 'direction':'neutral', 'evidence_item_ids':[item['id']]})
    codes = {f['rule_id'] for f in validate_record(record)['findings']}
    assert 'CBR006' in codes


@pytest.mark.parametrize('case', ['missing_rule','unknown_rule','wrong_profile','flags_string','duplicate_yaml'])
def test_invalid_policy_fails_explicitly(tmp_path, case):
    policy = yaml.safe_load(default_policy_path().read_bytes())
    if case == 'missing_rule': del policy['rules']['CBR009']
    elif case == 'unknown_rule': policy['rules']['CBR999'] = {'enabled':True,'severity':'error'}
    elif case == 'wrong_profile': policy['profile'] = 'unrelated'
    elif case == 'flags_string': policy['rules']['CBR007']['prohibited_scope_flags'] = 'mixed'
    path=tmp_path/'policy.yaml'; text=yaml.safe_dump(policy)
    if case == 'duplicate_yaml': text += '\nrules: {}\n'
    path.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError): validate_record(valid(),policy_path=path)


@pytest.mark.parametrize('table', ['source_records','concepts','resolved_source_names','name_link_overrides'])
def test_adapter_rejects_duplicate_identifiers(tmp_path, table):
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    with closing(sqlite3.connect(database)) as db, db:
        if table=='resolved_source_names':
            db.execute('CREATE TABLE duplicate_resolution AS SELECT * FROM resolved_source_names')
            db.execute('INSERT INTO duplicate_resolution SELECT * FROM duplicate_resolution LIMIT 1')
            db.execute('DROP VIEW resolved_source_names')
            db.execute('CREATE VIEW resolved_source_names AS SELECT * FROM duplicate_resolution')
        else:
            view_sql = db.execute("SELECT sql FROM sqlite_master WHERE name='resolved_source_names'").fetchone()[0]
            db.execute('DROP VIEW resolved_source_names')
            db.execute(f'CREATE TABLE duplicate_rows AS SELECT * FROM "{table}"')
            db.execute(f'INSERT INTO duplicate_rows SELECT * FROM "{table}" LIMIT 1')
            db.execute(f'DROP TABLE "{table}"')
            db.execute(f'ALTER TABLE duplicate_rows RENAME TO "{table}"')
            db.execute(view_sql)
    with pytest.raises(ValueError,match='[Dd]uplicate'): export_canine_panel(database,manifest,output)
    assert not output.exists()


def test_adapter_rejects_wal_sidecar_before_reading(tmp_path):
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
        db.execute("UPDATE concepts SET source_name='Pending WAL name' WHERE source_concept_id='VBO:LAB'");db.commit()
        assert Path(str(database)+'-wal').stat().st_size > 0
        with pytest.raises(ValueError,match='snapshot|sidecar|WAL'): export_canine_panel(database,manifest,output)
    assert not output.exists()


@pytest.mark.parametrize('field,value', [('requested_uses_default','display_name'),('requested_uses_by_source',[]),('ontology_version',42),('concept_status_default','typo'),('typo_field',True)])
def test_manifest_contract_is_checked_before_output(tmp_path,field,value):
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    data=yaml.safe_load(manifest.read_bytes());data[field]=value;manifest.write_text(yaml.safe_dump(data),encoding='utf-8')
    with pytest.raises(ValueError): export_canine_panel(database,manifest,output)
    assert not output.exists()


@pytest.mark.parametrize('direction', ['supports','neutral'])
def test_evidence_strength_uses_only_supporting_items(direction):
    record=valid()
    for item in record['evidence_items']: item['extraction_method']='normalized_string_match'
    extra=copy.deepcopy(record['evidence_items'][0]);extra['id']='bioev:manual';extra['extraction_method']='manual_curation'
    record['evidence_items'].append(extra)
    record['statement']['evidence_lines'].append({'id':'bioev:extra','direction':direction,'evidence_item_ids':[extra['id']]})
    codes={f['rule_id'] for f in validate_record(record)['findings']}
    assert ('CBR005' in codes) == (direction=='neutral')


def test_regional_equivalence_requires_scope_evidence():
    record=valid();record['statement']['subject_label']['scope_hint']='regional_population'
    assert 'CBR006' in {f['rule_id'] for f in validate_record(record)['findings']}


def test_relationship_cannot_become_sample_label():
    record=valid();record['requested_uses']=['display_name','frequency_label_mapping']
    record['statement']['statement_type']='breed_relationship';record['statement']['predicate']='variety_of'
    report=validate_record(record)
    assert {d['use']:d['admission_status'] for d in report['use_decisions']} == {'display_name':'admitted','frequency_label_mapping':'rejected'}


def test_custom_schema_cannot_relax_baseline(tmp_path):
    from bioevidence_validator.engine import RecordValidator
    schema=tmp_path/'loose.yaml'
    schema.write_text("id: https://example.org/loose\nname: loose\nprefixes:\n  linkml: https://w3id.org/linkml/\nimports: [linkml:types]\ndefault_range: string\nclasses:\n  Loose:\n    tree_root: true\n    attributes:\n      requested_uses:\n        multivalued: true\n",encoding='utf-8')
    report=RecordValidator(schema_path=schema).validate({'requested_uses':['display_name']})
    assert report['overall_status']=='rejected'
    assert [s['role'] for s in report['schema_sources']]==['baseline','extension']


def test_compiled_context_freezes_policy_after_file_changes(tmp_path):
    from bioevidence_validator.engine import RecordValidator
    policy=tmp_path/'policy.yaml';policy.write_bytes(default_policy_path().read_bytes())
    context=RecordValidator(policy_path=policy);before=context.validate(valid())
    policy.write_text('broken: policy',encoding='utf-8')
    after=context.validate(valid())
    assert after['overall_status']=='admitted'
    assert after['policy_sha256']==before['policy_sha256']
    assert after['schema_sha256']==before['schema_sha256']


@pytest.mark.parametrize('filename',['canine_breed_catalog_v0.1.yaml','canine_breed_catalog_v0.2.yaml'])
def test_archived_policy_files_still_load(filename):
    assert validate_record(valid(),policy_path=default_policy_path().with_name(filename))['overall_status']=='admitted'


def test_adapter_compiles_once_and_accounts_for_limit(tmp_path,monkeypatch):
    from bioevidence_validator import engine
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    original=engine.generate_json_schema;calls=[]
    def counted(*a,**kw): calls.append(1);return original(*a,**kw)
    monkeypatch.setattr(engine,'generate_json_schema',counted)
    summary=export_canine_panel(database,manifest,output,limit=2)
    assert len(calls)==1
    assert summary['total_input_records']==4 and summary['input_records_considered']==2
    assert summary['exported_records']+summary['skipped_records']==2
    records=[json.loads(line) for line in (output/'records.jsonl').read_text(encoding='utf-8').splitlines()]
    reports=[json.loads(line) for line in (output/'validation_reports.jsonl').read_text(encoding='utf-8').splitlines()]
    for record,report in zip(records,reports):
        assert any(item['evidence_type']=='resolved_source_name_row' for item in record['evidence_items'])
        assert report['schema_sha256']==summary['schema_sha256']
        assert report['policy_sha256']==summary['policy_sha256']
        canonical=json.dumps(record,sort_keys=True,separators=(',',':')).encode()
        import hashlib
        assert report['input_sha256']==hashlib.sha256(canonical).hexdigest()
    for name,digest in summary['outputs'].items():
        assert hashlib.sha256((output/name).read_bytes()).hexdigest()==digest


def test_changed_database_never_publishes_success(tmp_path,monkeypatch):
    from bioevidence_validator import canine_panel_adapter as adapter
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    original=adapter._make_record;changed=False
    def mutate(*a,**kw):
        nonlocal changed
        if not changed:
            with closing(sqlite3.connect(database)) as db, db: db.execute("UPDATE concepts SET source_name='Modified'")
            changed=True
        return original(*a,**kw)
    monkeypatch.setattr(adapter,'_make_record',mutate)
    with pytest.raises(ValueError,match='changed during export'): export_canine_panel(database,manifest,output)
    assert not output.exists()


def test_partial_export_has_no_completion_summary(tmp_path,monkeypatch):
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    original=Path.write_bytes
    def fail(path,data):
        if path.name=='validation_reports.jsonl': raise OSError('simulated full disk')
        return original(path,data)
    monkeypatch.setattr(Path,'write_bytes',fail)
    with pytest.raises(OSError): export_canine_panel(database,manifest,output)
    assert not (output/'summary.json').exists()


def test_cli_schema_compilation_failure_is_structured(tmp_path,capsys):
    from bioevidence_validator.cli import main
    schema=tmp_path/'bad.yaml';schema.write_text('broken: [',encoding='utf-8')
    assert main(['generate-schema','--schema',str(schema),'--output',str(tmp_path/'out.json')])==3
    assert json.loads(capsys.readouterr().err)['error']=='input_or_execution_error'


def test_cli_manifest_validation_failure_is_structured(tmp_path,capsys):
    from bioevidence_validator.cli import main
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    data=yaml.safe_load(manifest.read_bytes());data['requested_uses_by_source']=[]
    manifest.write_text(yaml.safe_dump(data),encoding='utf-8')
    assert main(['export-canine-panel',str(database),'--manifest',str(manifest),'--output',str(output)])==3
    assert json.loads(capsys.readouterr().err)['error']=='input_or_execution_error'
    assert not output.exists()


@pytest.mark.parametrize('value',['maybe',42,'unknown'])
def test_adapter_never_guesses_boolean_evidence(tmp_path,value):
    database,manifest,output=tmp_path/'db.sqlite',tmp_path/'manifest.yaml',tmp_path/'out'
    make_database(database);make_manifest(manifest)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('UPDATE concepts SET source_obsolete_flag=?',(value,))
    with pytest.raises(ValueError,match='boolean evidence'): export_canine_panel(database,manifest,output)
    assert not output.exists()


def test_canonical_curie_cannot_have_trailing_newline():
    record=valid();record['statement']['object_breed']['concept_id']='VBO:0000720\n'
    record['statement']['subject_label']['candidate_concept_ids']=['VBO:0000720\n']
    assert validate_record(record)['overall_status']=='rejected'


def test_returned_metadata_cannot_mutate_future_reports():
    from bioevidence_validator.engine import RecordValidator
    context=RecordValidator();report=context.validate(valid())
    expected=report['schema_sources'][0]['sha256']
    report['schema_sources'][0]['sha256']='tampered'
    assert context.validate(valid())['schema_sources'][0]['sha256']==expected


def test_deep_json_fails_with_cli_operational_status(tmp_path,capsys):
    from bioevidence_validator.cli import main
    source=tmp_path/'deep.json';source.write_text('['*5000+']'*5000,encoding='utf-8')
    assert main(['validate',str(source)])==3
    assert json.loads(capsys.readouterr().err)['error']=='input_or_execution_error'
