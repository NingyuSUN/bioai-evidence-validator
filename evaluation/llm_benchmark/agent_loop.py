"""Scenario 2: an agent retrieves literature itself, and bioevidence checks what it submits.

    uv run --frozen python evaluation/llm_benchmark/agent_loop.py run --output artifacts/agent-pilot   # network
    uv run --frozen python evaluation/llm_benchmark/agent_loop.py collect --output artifacts/agent-pilot \
        --results evaluation/llm_benchmark/results/agent-pilot
    uv run --frozen python evaluation/llm_benchmark/agent_loop.py score --results evaluation/llm_benchmark/results/agent-pilot

The agent gets a CIViC-style claim and three tools, run by this harness rather than the model's CLI (so every
model has the same tools and every step is logged): `search` (PubMed), `read` (a paper's open full text, or
its abstract) and `submit` (a decision with up to three citations: PMID, title, exact quote, and the quote's
stance toward the claim). The decision may be "conflicting" when the papers disagree. A submission is built
into an evidence record, one evidence line per stance, and validated with the literature grounder under the
CIViC literature profile: a record whose lines disagree goes to an expert (BEV004), however the agent decided.
Any other submission that is not admitted gets the verifier's reasons back, and the agent may revise and
submit again (at most three submissions, eight actions). Its first submission is made before any feedback, so one run yields:
the agent alone (first submission as given), the agent behind a bioevidence gate (first submission checked)
and the agent in a bioevidence feedback loop (final submission checked).

NCBI responses are cached in `<output>/cache` (outside the repository) and downloads stop at 100 MB.
Transcripts, which contain paper text, stay there too; the repository keeps final submissions and what
was verified.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from bioevidence_validator import literature
from bioevidence_validator.engine import RecordValidator
from bioevidence_validator.grounding import SnapshotStore, SourceBytesGrounder

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import literature_suite  # noqa: E402
import run_models  # noqa: E402
import score_claims  # noqa: E402

MAX_STEPS, MAX_SUBMITS, CAP_BYTES = 8, 3, 100 * 1024 * 1024
READ_CHARS, SNIPPET_CHARS = 30_000, 300
FIELDS = ["thought", "action", "query", "pmid", "decision", "citations", "rationale"]
DECISIONS = ["supports", "does_not_support", "conflicting", "stop"]
STANCES = ["supports", "contradicts", "neutral"]
CITATION = {"type": "object", "additionalProperties": False, "required": ["pmid", "title", "quote", "stance"],
            "properties": {"pmid": {"type": "string"}, "title": {"type": "string"}, "quote": {"type": "string"},
                           "stance": {"type": "string", "enum": STANCES}}}
STEP_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": FIELDS,
    "properties": {
        "thought": {"type": "string"},
        "action": {"type": "string", "enum": ["search", "read", "submit"]},
        "query": {"type": "string"}, "pmid": {"type": "string"},
        "decision": {"type": "string"},  # checked in code: Gemini rejects an empty enum value
        "citations": {"type": "array", "items": CITATION},
        "rationale": {"type": "string"},
    },
}
PROMPT = """You are a literature curation agent for a cancer variant database. Find out what the published \
literature says about the claim below using the tools, looking for evidence both for and against it, then \
submit an evidence record: your decision and up to three citations (PMID, title, an exact quote from text you \
read, and the quote's stance toward the claim). Citations are checked against the papers.

Claim:
{claim}

Tools (one action per reply):
- search: search PubMed; set "query".
- read: read a paper by PMID (its open full text if there is one, otherwise its abstract); set "pmid".
- submit: submit the record; set "decision" ("supports" or "does_not_support" when the papers you read agree, \
"conflicting" when they disagree, or "stop" if the literature does not settle the claim) and "citations", each \
with "stance": "supports", "contradicts" or "neutral" toward the claim.
Leave the fields an action does not use empty. Keep "thought" to one sentence. Use only these tools, not \
your own tools, files or the web. You have {left} action(s) left{submits}.

History:
{history}"""


def wsl_path(path: Path) -> str:
    text = str(path).replace("\\", "/")
    return f"/mnt/{text[0].lower()}{text[2:]}" if re.match(r"^[A-Za-z]:/", text) else text


# Which Claude Code install answers Claude calls: "wsl" (the default; the Windows CLI's login can expire mid-run) or
# "windows", the native install with its own account, used when the WSL account's quota is spent.
CLAUDE_HOSTS = ("wsl", "windows")
claude_host = "wsl"


def call_model(key: str, prompt: str, timeout: int = 600, schema: dict | None = None) -> tuple[dict, list[str]]:
    """One fresh CLI call answering `schema` (default STEP_SCHEMA), through the WSL installs of Claude Code, Codex and Antigravity."""
    spec = run_models.MODELS[key]
    with tempfile.TemporaryDirectory(prefix="agent-", dir=Path("C:/t/agent-work")) as directory:
        work = Path(directory)
        (work / "schema.json").write_text(json.dumps(schema or STEP_SCHEMA), encoding="utf-8")
        (work / "prompt.txt").write_text(prompt, encoding="utf-8")
        schema_file, folder = wsl_path(work / "schema.json"), wsl_path(work)
        if spec["cli"] == "claude" and claude_host == "windows":
            argv, stdin = run_models.claude_command(spec["model"], schema or STEP_SCHEMA, work / "schema.json", prompt,
                                                    timeout)
            answer, tools, _ = run_models.claude_parse(run_models.execute(argv, stdin, work, timeout + 60).stdout, work)
            return answer, tools
        if spec["cli"] == "claude":  # the WSL install
            command = ("PATH=$(ls -d ~/.nvm/versions/node/*/bin | tail -1):$PATH claude -p --model "
                       f"{spec['model']} --tools '' --strict-mcp-config --no-session-persistence --output-format json "
                       f"--json-schema \"$(cat {schema_file})\" < prompt.txt")
            parse = run_models.claude_parse
        elif spec["cli"] == "codex":
            disable = " ".join(f"--disable {f}" for f in run_models.CODEX_DISABLED)
            command = (f"codex exec -m {spec['model']} --ignore-user-config {disable} --sandbox read-only "
                       f"--skip-git-repo-check --ephemeral --json --output-schema {schema_file} -o last.json - < prompt.txt")
            parse = run_models.codex_parse
        else:
            command = (f"agy --model {spec['model']} --output-format stream-json --json-schema {schema_file} --sandbox "
                       f"--print-timeout {timeout}s --print \"$(cat prompt.txt)\"")
            parse = run_models.gemini_parse
        done = subprocess.run(["wsl.exe", "-e", "bash", "-lc", f"export PATH=$HOME/.local/bin:$PATH; cd {folder} && {command}"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 60)
        answer, tools, _ = parse(done.stdout, work)
        return answer, tools


def check_step(answer: Any) -> dict:
    if not isinstance(answer, dict) or set(answer) != set(FIELDS) or answer["action"] not in ("search", "read", "submit"):
        raise ValueError("invalid step")
    if answer["action"] == "submit":
        if answer["decision"] not in DECISIONS:
            raise ValueError("a submission needs a decision: supports, does_not_support, conflicting or stop")
        if not isinstance(answer["citations"], list) or not all(
                isinstance(c, dict) and set(c) == set(CITATION["required"]) and all(isinstance(v, str) for v in c.values())
                and c["stance"] in STANCES for c in answer["citations"]):
            raise ValueError("each citation needs pmid, title, quote and a stance: supports, contradicts or neutral")
    return answer


class Library:
    """PubMed search and reading through NCBI E-utilities, cached, with a download cap; plus the verifier."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.snapshots = folder / "snapshots"
        (folder / "http").mkdir(parents=True, exist_ok=True)
        self.snapshots.mkdir(parents=True, exist_ok=True)
        path = self.snapshots / literature.CATALOG
        self.catalog = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "works": {}}
        self.lock, self.net = threading.RLock(), threading.Lock()
        self.plain = literature.http_fetch()
        self.downloaded = sum(p.stat().st_size for p in (folder / "http").iterdir())

    def fetch(self, url: str) -> bytes:
        cached = self.folder / "http" / hashlib.sha256(url.encode()).hexdigest()
        if cached.exists():
            return cached.read_bytes()
        with self.net:
            if self.downloaded > CAP_BYTES:
                raise OSError("download cap reached")
            for attempt in range(4):
                try:
                    time.sleep(0.35)
                    data = self.plain(url)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code < 429 or attempt == 3:
                        raise
                    time.sleep(2 ** (attempt + 1))
            self.downloaded += len(data)
        cached.write_bytes(data)
        return data

    def abstracts(self, pmids: list[str]) -> dict[str, dict]:
        if not pmids:
            return {}
        root = ET.fromstring(self.fetch(literature._eutils("efetch", db="pubmed", id=",".join(pmids), retmode="xml")))
        out = {}
        for article in root.iter("PubmedArticle"):
            pmid = article.findtext(".//PMID") or ""
            out[pmid] = {"title": "".join(article.find(".//ArticleTitle").itertext()) if article.find(".//ArticleTitle")
                         is not None else "", "journal": article.findtext(".//Journal/Title") or "",
                         "year": article.findtext(".//PubDate/Year") or "",
                         "abstract": literature.normalize(" ".join("".join(a.itertext()) for a in article.iter("AbstractText")))}
        return out

    def search(self, query: str) -> str:
        found = json.loads(self.fetch(literature._eutils("esearch", db="pubmed", term=query, retmax="8", retmode="json")))
        ids = found.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return f"No PubMed results for {query!r}."
        hits = self.abstracts(ids)
        return "\n".join(f"- PMID {p}: {hits.get(p, {}).get('title', '?')} ({hits.get(p, {}).get('journal', '')} "
                         f"{hits.get(p, {}).get('year', '')}). {hits.get(p, {}).get('abstract', '')[:SNIPPET_CHARS]}"
                         for p in ids)

    def resolve(self, key: str) -> dict:
        with self.lock:
            if key not in self.catalog["works"]:
                now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
                self.catalog["works"][key] = literature.resolve(key, self.snapshots, self.fetch, now, resolver="ncbi",
                                                                compress=True)
                (self.snapshots / literature.CATALOG).write_text(json.dumps(self.catalog, indent=2, sort_keys=True) + "\n",
                                                                 encoding="utf-8", newline="\n")
            return self.catalog["works"][key]

    def read(self, pmid: str) -> str:
        key = score_claims.pmid_of(pmid)
        if not key:
            return f"{pmid!r} is not a PMID."
        entry = self.resolve(key)
        store = SnapshotStore.from_directory(self.snapshots)
        meta = literature.parse_metadata(entry["resolver"], store.get(entry["metadata_sha256"]) or b"")
        if not meta["found"]:
            return f"PubMed has no record {key}."
        if entry["fulltext_sha256"]:
            blocks = literature.jats_blocks(store.get(entry["fulltext_sha256"]) or b"")
            text = "\n".join(f"## {t}" if kind == "title" else t for _, kind, t in blocks)
            return f"{meta['title']} ({key}), open full text:\n{text[:READ_CHARS]}"
        if entry.get("abstract_sha256"):
            abstract = " ".join(t for i, t in literature.pubmed_abstract(store.get(entry["abstract_sha256"]) or b"")
                                if i != "title")
            return f"{meta['title']} ({key}). No open full text; abstract only:\n{abstract}"
        return f"{meta['title']} ({key}). Neither open full text nor an abstract is available."

    def check(self, task: dict, submission: dict) -> dict:
        """Validate the submission as a record; return the status and the reasons, per citation."""
        for cited in submission["citations"]:
            if key := score_claims.pmid_of(cited["pmid"]):
                self.resolve(key)
        stances = {c["stance"] for c in submission["citations"]}
        with self.lock:
            catalog = json.loads(json.dumps(self.catalog))
        verifier = score_claims.Verifier.__new__(score_claims.Verifier)
        verifier.store, verifier.catalog = SnapshotStore.from_directory(self.snapshots), catalog
        verifier.validator = RecordValidator(profile=score_claims.CASE / "profile.yaml", grounders=[
            SourceBytesGrounder(verifier.store), literature.LiteratureGrounder(verifier.store, catalog)])
        citations = [verifier.citation(c) for c in submission["citations"]]
        if submission["decision"] == "conflicting" and not {"supports", "contradicts"} <= stances:
            # The harness's own check: the record would state the claim with one side only.
            return {"status": "rejected", "codes": ["STANCE"], "citations": citations,
                    "reasons": ["A 'conflicting' decision needs a citation that supports the claim and one that "
                                "contradicts it."]}
        record = verifier.record(task, submission)
        if record is None:
            return {"status": "not_submitted", "codes": [], "reasons": ["The record has no decision or no citation."]}
        report = verifier.validator.validate(record)
        reasons = []
        for f in report["findings"]:
            if f["rule_id"] == "BEV004":
                continue  # disagreeing evidence is not an error to fix: it goes to an expert (see `to_expert`)
            match = re.match(r"\$\.(?:evidence_items|source_artifacts)\[(\d+)\]", f["field_path"])
            where = f"citation {int(match.group(1)) + 1}: " if match else ""
            reasons.append(where + f["message"])
        return {"status": report["overall_status"], "codes": sorted({f["rule_id"] for f in report["findings"]}),
                "reasons": sorted(set(reasons)), "citations": citations}


def episode(key: str, task: dict, library: Library) -> dict:
    """One agent run on one task, with feedback after each submission that is not admitted."""
    history, steps, submissions = [], [], []
    for step in range(1, MAX_STEPS + 1):
        left = MAX_STEPS - step + 1
        submits = f", including {MAX_SUBMITS - len(submissions)} submission(s)"
        prompt = PROMPT.format(claim=literature_suite.claim_lines(task["claim"]), left=left, submits=submits,
                               history="\n".join(history) or "(nothing yet)")
        started, record = time.monotonic(), {"step": step}
        try:
            answer, tools = None, []
            for _ in range(2):  # one retry on an invalid answer or a tool call of the CLI's own
                try:
                    answer, tools = call_model(key, prompt)
                    answer = check_step(answer)
                    if not tools:
                        break
                except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                    answer, record["error"] = None, f"{type(exc).__name__}: {exc}"[:300]
            if answer is None:
                raise ValueError(record.get("error", "no valid answer"))
            record.update(action=answer["action"], cli_tools=tools)
            if answer["action"] == "search":
                observation = library.search(answer["query"])
                record["query"] = answer["query"]
            elif answer["action"] == "read":
                observation = library.read(answer["pmid"])
                record["pmid"] = answer["pmid"]
            else:
                submission = {k: answer[k] for k in ("decision", "citations", "rationale")}
                submission["citations"] = submission["citations"] + carried(submissions, submission["citations"])
                verdict = library.check(task, submission)
                submissions.append({"step": step, "submission": submission, "verdict": verdict})
                record["status"] = verdict["status"]
                if (verdict["status"] == "admitted" or submission["decision"] == "stop" or len(submissions) >= MAX_SUBMITS
                        or to_expert(verdict)):
                    steps.append({**record, "seconds": round(time.monotonic() - started, 1)})
                    break
                observation = ("The verifier did not admit the record. Reasons: " + " | ".join(verdict["reasons"])
                               + " Verified citations stay in the record; you may fix or replace the others and submit "
                               f"again ({MAX_SUBMITS - len(submissions)} left).")
        except (ValueError, OSError, ET.ParseError) as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            observation = f"The action failed: {record['error']}"
        steps.append({**record, "seconds": round(time.monotonic() - started, 1)})
        history.append(f"[{step}] {record.get('action', 'error')} {record.get('query') or record.get('pmid') or ''}\n"
                       f"→ {observation}")
        history = compact(history)
    return {"model": key, "task_id": task["task_id"], "steps": steps, "submissions": submissions,
            "finished_at": dt.datetime.now(dt.UTC).isoformat()}


def carried(submissions: list[dict], citations: list[dict]) -> list[dict]:
    """Citations verified in an earlier submission and left out of this one. They stay in the record: a revision may
    fix or replace what failed, but not withdraw verified evidence, such as a quote against the decision."""
    def same(c: dict) -> tuple:
        return score_claims.pmid_of(c["pmid"]), literature.normalize(c["quote"])

    seen, kept = {same(c) for c in citations}, []
    for previous in submissions:
        for cited, check in zip(previous["submission"]["citations"], previous["verdict"].get("citations", []), strict=False):
            if check["category"] == "quote_found" and same(cited) not in seen:
                seen.add(same(cited))
                kept.append(cited)
    return kept


def to_expert(verdict: dict) -> bool:
    """Disagreeing evidence lines, and nothing else wrong: the record goes to an expert as it is. This is not fed
    back, so the agent is never pushed to drop the evidence against its decision."""
    return verdict["status"] == "review_required" and verdict["codes"] == ["BEV004"]


def compact(history: list[str]) -> list[str]:
    """Keep the two most recent reads in full; shorten older ones so the prompt stays bounded."""
    reads = [i for i, h in enumerate(history) if h.split("]", 1)[1].startswith(" read")]
    for i in reads[:-2]:
        head, _, body = history[i].partition("→ ")
        history[i] = head + "→ " + body[:400] + " … (text shortened; read again if needed)"
    return history


def run(output: Path, models: list[str], workers: int, limit: int | None) -> int:
    tasks = [json.loads(line) for line in (literature_suite.TASKS / "pilot.jsonl").read_text(encoding="utf-8").splitlines()]
    tasks = tasks[:limit] if limit else tasks
    library = Library(output / "cache")
    Path("C:/t/agent-work").mkdir(parents=True, exist_ok=True)
    jobs = []
    for n in range(len(tasks)):
        for key in models:
            path = output / "episodes" / key / f"{tasks[n]['task_id']}.json"
            if not path.exists():
                jobs.append((key, tasks[n], path))
    print(f"{len(jobs)} episode(s) to run; {library.downloaded / 1e6:.1f} MB downloaded so far", flush=True)

    # Claude models share the operator's Claude usage limit: one episode at a time.
    slots = {key: threading.Semaphore(1 if run_models.MODELS[key]["cli"] == "claude" else workers) for key in models}

    def work(job):
        key, task, path = job
        with slots[key]:
            result = episode(key, task, library)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers * len(models)) as pool:
        for n, result in enumerate(pool.map(work, jobs), start=1):
            final = result["submissions"][-1]["verdict"]["status"] if result["submissions"] else "no submission"
            errors = sum("error" in s for s in result["steps"])
            print(f"[{n}/{len(jobs)}] {result['model']} {result['task_id']}: {len(result['steps'])} step(s), "
                  f"{len(result['submissions'])} submission(s), final {final}, {errors} error(s); "
                  f"{library.downloaded / 1e6:.1f} MB", flush=True)
    return 0


def collect(output: Path, results: Path) -> None:
    """Episodes without paper text: actions, and each submission with what bioevidence found."""
    rows = []
    for path in sorted((output / "episodes").glob("*/*.json")):
        e = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"model": e["model"], "task_id": e["task_id"],
                     "actions": [s.get("action", "error") for s in e["steps"]],
                     "errors": sum("error" in s for s in e["steps"]),
                     "seconds": round(sum(s["seconds"] for s in e["steps"]), 1),
                     "submissions": [{"step": s["step"], **s["submission"],
                                      "status": s["verdict"]["status"], "codes": s["verdict"]["codes"],
                                      "reasons": s["verdict"]["reasons"],
                                      "categories": [c["category"] for c in s["verdict"].get("citations", [])]}
                                     for s in e["submissions"]]})
    results.mkdir(parents=True, exist_ok=True)
    score_claims.write_jsonl(results / "episodes.jsonl", rows)
    score(results)


VIEWS = [("agent", "Agent alone (first submission)"), ("gate", "Agent + bioevidence gate (first submission)"),
         ("loop", "Agent + bioevidence feedback loop (final submission)")]


def view(row: dict, name: str) -> dict:
    """What a view delivers: a decision ("conflicting" included, or "stop"), its citations' categories, and whether it
    went to a human. Behind bioevidence, a record whose evidence lines disagree goes to an expert as conflicting."""
    subs = row["submissions"]
    if not subs:
        return {"final": "stop", "categories": [], "routed": False}
    first, last = subs[0], subs[-1]
    if name == "agent":
        return {"final": first["decision"], "categories": first["categories"], "routed": False}
    chosen = first if name == "gate" else last
    if chosen["status"] == "admitted":
        return {"final": chosen["decision"], "categories": chosen["categories"], "routed": False}
    if to_expert(chosen):
        return {"final": "conflicting", "categories": chosen["categories"], "routed": True}
    return {"final": "stop", "categories": [], "routed": chosen["decision"] != "stop"}


def score(results: Path) -> dict:
    rows = score_claims.load_jsonl(results / "episodes.jsonl")
    expected = score_claims.expected_directions()
    models = [m for m in score_claims.MODEL_NAMES if any(r["model"] == m for r in rows)]

    def metrics(mine: list[dict], name: str) -> dict:
        views = [(r, view(r, name)) for r in mine]
        delivered = [(r, v) for r, v in views if v["final"] != "stop"]
        return {
            "tasks": len(mine),
            "answered": score_claims.rate(len(delivered), len(mine)),
            "correct_decision": score_claims.rate(sum(v["final"] == expected[r["task_id"]] for r, v in views), len(mine)),
            "wrong_direction": score_claims.rate(sum(v["final"] in ("supports", "does_not_support") and
                                                     v["final"] != expected[r["task_id"]] for r, v in views), len(mine)),
            "conflicting": score_claims.rate(sum(v["final"] == "conflicting" for _, v in views), len(mine)),
            "invalid_citation": score_claims.rate(sum(any(c in score_claims.INVALID for c in v["categories"])
                                                      for _, v in delivered), len(delivered)),
            "only_verified_citations": score_claims.rate(sum(bool(v["categories"]) and all(c == "quote_found" for c in
                                                         v["categories"]) for _, v in delivered), len(delivered)),
            "routed_to_human": score_claims.rate(sum(v["routed"] for _, v in views), len(mine)),
        }
    results_by_model = {m: {name: metrics([r for r in rows if r["model"] == m], name) for name, _ in VIEWS}
                        for m in models}
    pooled = {name: metrics(rows, name) for name, _ in VIEWS}
    revised = [r for r in rows if len(r["submissions"]) > 1]
    rescued = sum(r["submissions"][0]["status"] != "admitted" and r["submissions"][-1]["status"] == "admitted"
                  for r in revised)
    stances = any("stance" in c for r in rows for s in r["submissions"] for c in s["citations"])
    summary = {"benchmark": "llm-literature-agent-v2" if stances else "llm-literature-agent-v1", "split": "pilot", "results": results_by_model, "pooled": pooled,
               "episodes": len(rows), "revised": len(revised), "rescued_by_feedback": rescued,
               "actions": {a: sum(r["actions"].count(a) for r in rows) for a in ("search", "read", "submit", "error")},
               "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2] if rows else None,
               "episodes_sha256": hashlib.sha256((results / "episodes.jsonl").read_bytes()).hexdigest()}
    (results / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                          newline="\n")
    (results / "summary.md").write_text(render(summary), encoding="utf-8", newline="\n")
    print(render(summary))
    return summary


def render(summary: dict) -> str:
    f = score_claims.fraction
    v2 = summary["benchmark"].endswith("v2")
    lines = [f"# Literature benchmark, scenario {'2b' if v2 else '2'}: an agent that searches and reads"
             f"{', with stances' if v2 else ''} (pilot set)", "",
             "The agent gets the claim and three tools (PubMed search, read a paper, submit). Bioevidence checks each "
             "submission; in the loop, its reasons go back to the agent, which may revise (at most three submissions, "
             "eight actions)." + (" Each citation carries its stance toward the claim, and the agent may decide "
                                  "\"conflicting\"; behind bioevidence, a record whose evidence lines disagree goes to "
                                  "an expert as conflicting." if v2 else ""), "",
             "| Model | View | Answered | Correct decision | Wrong direction | Conflicting | Answers with an invalid "
             "citation | Answers with only verified citations | Routed to a human |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    blocks = [(score_claims.MODEL_NAMES[m], v) for m, v in summary["results"].items()] + [("All models", summary["pooled"])]
    for name, views in blocks:
        for key, label in VIEWS:
            m = views[key]
            lines.append(f"| {name} | {label} | {f(m['answered'])} | {f(m['correct_decision'])} | "
                         f"{f(m['wrong_direction'])} | {f(m['conflicting'])} | {f(m['invalid_citation'])} | "
                         f"{f(m['only_verified_citations'])} | "
                         f"{f(m['routed_to_human'])} |")
    a = summary["actions"]
    lines += ["", f"{summary['episodes']} episodes; {a['search']} searches, {a['read']} reads, {a['submit']} submissions, "
              f"{a['error']} failed steps; median {summary['median_seconds']} s per episode. {summary['revised']} "
              f"episodes revised after feedback, {summary['rescued_by_feedback']} of them from not admitted to admitted.",
              "", "Invalid citation: no PMID, a PMID that does not exist, a retracted paper, a title that does not match "
              "the PMID, or a quote not in the paper (checked against its open full text, else its PubMed abstract).", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    r = steps.add_parser("run")
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--models", nargs="+", choices=list(run_models.MODELS), default=list(run_models.MODELS))
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--limit", type=int)
    c = steps.add_parser("collect")
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--results", type=Path, required=True)
    s = steps.add_parser("score")
    s.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.step == "collect":
        collect(args.output, args.results)
        return 0
    if args.step == "score":
        score(args.results)
        return 0
    return run(args.output, args.models, args.workers, args.limit)


if __name__ == "__main__":
    sys.exit(main())
