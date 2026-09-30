"""The CIViC literature case: pinned real papers, and the issue #20 negative controls replayed offline."""
import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/civic_literature"
sys.path.insert(0, str(EXAMPLE))
spec = importlib.util.spec_from_file_location("civic_literature_pipeline", EXAMPLE / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
sys.path.pop(0)


@pytest.fixture(scope="module")
def corpus():
    return pipeline.Corpus()


def test_corpus_is_pinned_and_openly_licensed(corpus):
    assert corpus.manifest["corpus"] and corpus.manifest["retracted"]
    for pmid in [*corpus.manifest["corpus"], *corpus.manifest["retracted"]]:
        entry = corpus.catalog["works"][f"pmid:{pmid}"]
        assert entry["license"] in ("cc by", "cc0") and corpus.store.verified(entry["fulltext_sha256"])
    for pmid in corpus.manifest["nonexistent_pmids"]:
        assert corpus.catalog["works"][f"pmid:{pmid}"]["fulltext_sha256"] is None
    assert {row["citation_id"] for row in corpus.evidence} == set(corpus.manifest["corpus"])


def test_changed_snapshot_is_refused(tmp_path, corpus):
    import shutil
    target = tmp_path / "sources"
    shutil.copytree(EXAMPLE / "sources", target)
    entry = corpus.catalog["works"][f"pmid:{sorted(corpus.manifest['corpus'])[0]}"]
    path = next((target / "snapshots").glob(entry["fulltext_sha256"] + "*"))
    path.write_bytes(gzip.compress(b"<article>changed after pinning</article>"))
    with pytest.raises(ValueError, match="missing or changed"):
        pipeline.Corpus(target)


def test_attribution_is_up_to_date(corpus):
    assert (EXAMPLE / "sources/ATTRIBUTION.md").read_text(encoding="utf-8") == pipeline.attribution(corpus)


@pytest.mark.parametrize("text,expected", [
    ("The mutation was associated with response.", "The mutation was not associated with response."),
    ("Tumours did not respond to the drug.", "Tumours did respond to the drug."),
    ("Response rates varied widely.", None),
])
def test_negate(text, expected):
    assert pipeline.negate(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Patients carrying the variant relapsed.", "Mice carrying the variant relapsed."),
    ("In mouse xenografts the drug worked.", "In human xenografts the drug worked."),
    ("Cell lines were resistant.", None),
])
def test_swap_species(text, expected):
    assert pipeline.swap_species(text) == expected


def test_quote_is_a_real_sentence(corpus):
    pmid = sorted(corpus.manifest["corpus"])[0]
    pid, sentence = pipeline.quote_for(corpus, pmid, None)
    assert any(sentence in text for p, text in corpus.paragraphs(pmid) if p == pid)
    assert 12 <= len(sentence.split()) <= 60


def test_controls_replay_the_committed_results(tmp_path):
    output = tmp_path / "run"
    result = subprocess.run([sys.executable, str(EXAMPLE / "run.py"), "--output", str(output)],
                            capture_output=True, text=True, encoding="utf-8", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    for expected in (EXAMPLE / "results").iterdir():
        assert expected.read_bytes() == (output / expected.name).read_bytes(), expected.name
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["controls"]["base"]["false_blocks"] == 0
    for control, stats in summary["controls"].items():
        if control != "base":
            assert stats["admitted"] == 0, control  # no negative control is ever admitted
