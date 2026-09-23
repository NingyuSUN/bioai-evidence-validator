"""Real-source integration and replay tests; no live network required."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/'examples/vbo_canine'
spec=importlib.util.spec_from_file_location('vbo_pipeline',EXAMPLE/'pipeline.py')
pipeline=importlib.util.module_from_spec(spec);spec.loader.exec_module(pipeline)


def test_pinned_names_and_natural_ambiguity():
    source=pipeline.DogNames()
    assert len(source.terms)==1537
    assert source.candidates('Labrador Retriever (Dog)')==['VBO:0200800']
    assert source.candidates('Border Collie')==['VBO:0007996','VBO:0200193']
    assert source.candidates('  BORDER  COLLIE ') == source.candidates('Border Collie')
    assert source.candidates('not a real breed label at all')==[]
    with pytest.raises(ValueError,match='No exact'):
        source.record('not a real breed label at all','missing')


def test_changed_snapshot_is_rejected_before_ingestion(tmp_path):
    (tmp_path/'sources').mkdir()
    for name in ['manifest.json','vbo-dogs.json']:
        (tmp_path/'sources'/name).write_bytes((EXAMPLE/'sources'/name).read_bytes())
    with (tmp_path/'sources/vbo-dogs.json').open('ab') as handle:handle.write(b' ')
    with pytest.raises(ValueError,match='hash mismatch'):pipeline.DogNames(tmp_path)


def test_full_example_replays_identically_and_exposes_boundaries(tmp_path):
    outputs=[tmp_path/'first',tmp_path/'second']
    for output in outputs:
        result=subprocess.run([sys.executable,str(EXAMPLE/'run.py'),'--output',str(output)],capture_output=True,text=True,encoding='utf-8',cwd=tmp_path)
        assert result.returncode==0,result.stderr
    for file in outputs[0].iterdir():
        assert file.read_bytes()==(outputs[1]/file.name).read_bytes(),file.name
    for expected in (EXAMPLE/'results').iterdir():
        assert expected.read_bytes() == (outputs[0]/expected.name).read_bytes(), expected.name
    summary=json.loads((outputs[0]/'summary.json').read_text(encoding='utf-8'))
    real=summary['cohorts']['real_source'];faults=summary['cohorts']['controlled_fault'];boundary=summary['cohorts']['trust_boundary']
    assert real['full']['n']==72 and real['full']['false_admissions']==0 and real['full']['false_blocks']==0
    assert real['schema_only']['false_admissions']==24
    assert faults['aggregate_quality']['false_admissions']==64
    assert faults['full']['false_admissions']==0 and faults['full']['n']==160
    assert boundary['full']['false_admissions']==16  # Explicitly measured trust limit, not omitted from results.
    manifest=json.loads((outputs[0]/'manifest.json').read_text())
    for name,expected in manifest.items():assert pipeline.digest((outputs[0]/name).read_bytes())==expected
    before=(outputs[0]/'manifest.json').read_bytes()
    rerun=subprocess.run([sys.executable,str(EXAMPLE/'run.py'),'--output',str(outputs[0])],capture_output=True,text=True)
    assert rerun.returncode!=0 and (outputs[0]/'manifest.json').read_bytes()==before


def test_ambiguity_is_visible_and_does_not_become_implicit_acceptance():
    source=pipeline.DogNames();record=source.record('Border Collie','border-collie')
    resolution=record['evidence_items'][1]
    assert json.loads(resolution['extracted_text'])['candidate_ids']==['VBO:0007996','VBO:0200193']
    report=pipeline.RecordValidator(profile=EXAMPLE/'profile.yaml').validate(record)
    assert report['overall_status']=='rejected'
    assert 'BEV007' in {f['rule_id'] for f in report['findings']}
